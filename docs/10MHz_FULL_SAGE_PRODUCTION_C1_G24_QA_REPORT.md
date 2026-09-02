# 10 MHz Full SAGE Production C1 G24 QA Report

## QA scope and conclusion

- Scene: `F1023_V120_D0121_P2`
- PRN: `G24`
- Tracking channel: `ch2` (channel `2`)
- Sample rate: `10,230,000 Hz` (10.23 MHz)
- QA conclusion: **PASS**
- Production result classification: `PASS_NO_CONFIRMED_MULTIPATH`

This independent QA reads final receipts, logs, run context, and Stage0–Stage4 CSV artifacts only. It does not rerun MATLAB/SAGE or open raw IQ.

## 1. Execution and contract verification

| Item | Value |
|---|---|
| Immutable request | `E:\GNSS_Multipath_Project\dataset_generation_logs\batch_sage_execution_requests\production_10mhz_c1_d0121p2_g24_20260818\execution_request.json` |
| Request SHA-256 | `0c1ae58403396f5c68d2c952c493dbc7733acc6989882b5de26ed8adaab19676` |
| Production manifest SHA-256 | `77c20c0ed6c84fa0348db429948a8bd4900b2e8d86a6d8843b159b9a7a35cf00` |
| Execution policy | `new_only=true`, `resume_allowed=false`, `max_parallel_matlab=1` |
| Wrapper receipt | `E:\GNSS_Multipath_Project\dataset_generation_logs\batch_sage_execution\windows_runner_receipts\windows_production_10mhz_c1_d0121p2_g24_20260818_20260818T130217990Z\` |
| Execution log | `E:\GNSS_Multipath_Project\dataset_generation_logs\batch_sage_execution\batch_sage_execution_20260818T130227Z\batch_execution_log.csv` |
| Status history | `ready -> running -> completed`, `matlab_exit_0_and_output_qa_pass` |
| Windows identity | `TJ-CHANNEL\Jing_` |
| PowerShell / MATLAB | `7.6.4` / `25.1.0.2802752` |
| MATLAB startup smoke | marker present, exit code `0` |
| Python/task exit code | `0` / `0` |
| Runtime | `11185.234 s` (about `186.42 min`) |

The recorded MATLAB command explicitly contains `Resume=false`. Exactly one approved task ran, with no error message and no protected namespace collision.

## 2. Output and Stage QA

Approved output: `E:\GNSS_Multipath_Project\scenes\F1023_V120_D0121_P2\sage_results\nav_sage_v2\G24\`.

All 21 expected files are present and non-empty. `run_context.json` matches scene `F1023_V120_D0121_P2`, PRN `G24`, channel `2`, sampling rate `10230000`, and the approved output directory.

| Stage | Observed rows / result |
|---|---:|
| Stage0 valid NAV symbols | 8265 |
| Stage0 40 ms windows | 8257 |
| Stage1 scanned windows | 8257 |
| Stage2 model-order rows | 208 (`52 x 4`) |
| Stage2 selected windows | 52 |
| Stage2 selected path rows | 52 |
| Stage3 persistence rows | 0 |
| Stage3 reliable centers | 0 |
| Stage4 joint summary rows | 0 (header-only valid zero-event output) |
| Stage4 joint path rows | 0 (header-only valid zero-event output) |

Independent checks passed:

- Stage0 window IDs are unique and Stage1 covers the Stage0 window set.
- Stage2 has exactly four model-order rows per selected window.
- Stage3 and Stage4 header-only CSVs are present and non-empty, representing no reliable centers entering joint confirmation.
- `joint_valid=1` rows: `0`; `joint_multipath_count>0` rows: `0`; `is_multipath=1` paths: `0`.
- Confirmed multipath events: **0**; confirmed multipath paths: **0**.

This is a complete valid zero-confirmed-event output under the current Stage4 criterion, not a physical LOS conclusion.

## 3. Artifact hashes

| File | Bytes | SHA-256 |
|---|---:|---|
| `doppler_sign.mat` | 1250 | `9e9eed16c331e9056e7d05c0346a4ab0c7d188738de284bf11626c16c9137818` |
| `G24_nav_sage_overview.png` | 257142 | `ba2e0331a8b8356c7786e336f53c52c12c5ce8c082950bb19f7c262b21e47191` |
| `run_context.json` | 1629 | `e64da1acd9873f2f22e0b00b7a6094b87c533428f2eb9ff0d2d59875f67ce027` |
| `run_context.mat` | 2497 | `f8166f46c7a09691b795b90d90434e034aa5d215a968e16e9811ec6a8bd549d4` |
| `stage0_nav_catalog.mat` | 526618 | `e1b2f0ec079815132676a1828ecbf8197ed3e9b99a5236398ba3f556566ac29b` |
| `stage0_valid_40ms_windows.csv` | 1222777 | `39a56159c2f0d29af3402f5e130f2212d637da8f966dfbfe3b3fe8001b223bb8` |
| `stage0_valid_symbols.csv` | 1328359 | `670a072ac57a1675bc054b2e04987bae0d437c0695b251535332ef1c111772fb` |
| `stage1_nav_fast_scan.csv` | 1903180 | `c80d74fdbf1b4b3a051ea50a1cabb19a55eb99575de9bc38f45c72d31d142f9` |
| `stage1_nav_fast_scan.mat` | 605236 | `a3d97cd287e03653b0c332e26521d2aabbce575e6064e0face8812517ca11368` |
| `stage1_nav_progress.mat` | 1156983 | `278d0569213a4f2536b5ddb70ebbd954c13664e565ea0237a141b736a8762559` |
| `stage2_model_orders.csv` | 25723 | `9e2539c2faa8f6a0ee07f7009694de59c10e2002418753e0637c3a903245ef6a` |
| `stage2_nav_progress.mat` | 51893 | `a81146864974d742c96406bbd107f082638d4d4d9443044460c36d51397a3a57` |
| `stage2_nav_sage_L1_L4.mat` | 64110 | `f7afeb61589993de82560b9d56254bb14205145bee3504b7f1d459576fed642e` |
| `stage2_selected_paths.csv` | 3232 | `5503eb171c8dfd8459cd23a198f83a84c3bdda93db489bf9788849882378ede3` |
| `stage2_selected_windows.csv` | 4237 | `64fcf38bdbd988d114c9f651fa4ca583357ccef30143cda06f6140059ed0dc47` |
| `stage3_nav_persistence.mat` | 2355 | `5478dbfdd05a03142f7b2932cf2b3c4c8a569ef11ee0ba04f0d41a0b0adbd6f7` |
| `stage3_persistence.csv` | 201 | `b8b42f66dab13e98d3f8c988ac8c9bd49df17792c3919fa1a6e0846f4cea2d5f` |
| `stage3_reliable_centers.csv` | 98 | `99ebc241ddcbf1d027faf0c0e162731f1a867f7781748f12efaf953d62ad8228` |
| `stage4_joint_paths.csv` | 162 | `3d0ec7b85be05f1ff6be8b9373e0ca0e35cf69ad4e51d22c215af23b35a0b6ea` |
| `stage4_joint_summary.csv` | 208 | `8d4610659bd8e3c52795d40337780661c6c4501d04ba6e840ffc5652d8354151` |
| `stage4_nav_joint_100ms.mat` | 2516 | `d203f3246c19b20dd3984af203bae97d2fd6b0f7b9c915c161f5816e1f66821f` |

## 4. Decision

G24 is accepted as a completed, QA-passed production task with zero confirmed multipath events under the strict Stage4 rule. No Paper/VTC scientific update is required for this zero-confirmed result. The manifest and production source remain unchanged. This report does not authorize another Codex-managed task; subsequent scheduling is delegated only to the independently verified unattended runner.
