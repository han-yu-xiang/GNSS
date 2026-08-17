# T1-3 Independent QA Report

- QA date: 2026-08-15
- Task: `F1023_v90_D0117_P7/G11/ch6/10.23 MHz`
- Environment: Mountain/Valley
- Geometry context: MID; scene-level mean elevation approximately `35.0°`
- QA mode: read-only independent QA
- Raw IQ content read: no
- MATLAB/SAGE rerun: no

## Sources

- Immutable request: `dataset_generation_logs/batch_sage_execution_requests/vtc_priority_t1_3_v90p7_g11_20260814/execution_request.json`
- Request SHA-256: `7a1361445855244ca6ed6f9f640debe1533981c7d4490bab52f45132fb170d47`
- Execution log: `dataset_generation_logs/batch_sage_execution/batch_sage_execution_20260815T132956Z/batch_execution_log.csv`
- Execution receipt: `dataset_generation_logs/batch_sage_execution/windows_runner_receipts/vtc_priority_t1_3_v90p7_g11_20260814_20260815T132728506Z/execution_receipt.json`
- Environment receipt: `dataset_generation_logs/batch_sage_execution/windows_runner_receipts/vtc_priority_t1_3_v90p7_g11_20260814_20260815T132728506Z/environment_receipt.json`
- Output: `scenes/F1023_v90_D0117_P7/sage_results/nav_sage_v2/G11`

## Execution Contract QA

**Execution Contract QA = PASS**

| Check | Result |
|---|---|
| Execution ID | `batch_sage_execution_20260815T132956Z` |
| Request identity/SHA | PASS; request ID and SHA match receipt, log, and request |
| Manifest/task provenance | PASS; manifest SHA `77c20c0e...cf00`; canonical task SHA `e4e72150...da8bd` |
| Pipeline hash | PASS; `5ff00366...b4b0ab` |
| Executor hash | PASS; `bab7a042...b08f1b` |
| Windows wrapper hash | PASS; `dd8afb1b...1143f3` |
| Windows identity | PASS; `TJ-CHANNEL\\Jing_` |
| PowerShell | PASS; `7.6.4` |
| MATLAB | PASS; R2025a file version `25.1.0.2802752` |
| MATLAB startup smoke | PASS; marker present and exit code `0`; stderr empty |
| Python executor | PASS; exit code `0` |
| Task | PASS; status `completed`, exit code `0`, empty error message |
| Runtime | `4901.428 s` (approximately `81.69 min`) |
| Resume contract | PASS; actual invocation contains `'Resume', false`; no true-valued Resume invocation found |

The wrapper receipt does not persist a separate wrapper-process exit-code field. The successful `approved_task_completed=true`, Python exit code `0`, task status `completed`, and empty error message provide consistent evidence of successful wrapper completion; this is recorded as a receipt observability limitation, not inferred as a scientific result.

## New-only Policy QA

**New-only Policy QA = PASS**

- The immutable preflight recorded the target output namespace as absent before execution.
- `new_only=true` and `resume_allowed=false` matched the request and executor receipt.
- The active global lock is absent after completion.
- The executor selected exactly one task; no other task was launched.
- The task log contains no evidence of `Stage loaded`, `resumed`, checkpoint reuse, previous-result loading, or existing-output reuse.
- The Stage1/Stage2 progress MAT files are current-run progress artifacts, not evidence of startup checkpoint reuse.
- The output path is the fixed new namespace `scenes/F1023_v90_D0117_P7/sage_results/nav_sage_v2/G11`; no legacy/reference namespace was selected.

## Artifact Completeness QA

**Artifact Completeness = PASS**

The target directory contains exactly 21 expected non-empty files:

`run_context.json`, `run_context.mat`, `stage0_valid_symbols.csv`, `stage0_nav_catalog.mat`, `stage0_valid_40ms_windows.csv`, `doppler_sign.mat`, `stage1_nav_fast_scan.csv`, `stage1_nav_fast_scan.mat`, `stage1_nav_progress.mat`, `stage2_model_orders.csv`, `stage2_selected_windows.csv`, `stage2_selected_paths.csv`, `stage2_nav_sage_L1_L4.mat`, `stage2_nav_progress.mat`, `stage3_persistence.csv`, `stage3_reliable_centers.csv`, `stage3_nav_persistence.mat`, `stage4_joint_summary.csv`, `stage4_joint_paths.csv`, `stage4_nav_joint_100ms.mat`, and `G11_nav_sage_overview.png`.

All CSVs have readable headers and rows. All six MAT artifacts load successfully with the available MATLAB-compatible reader. `run_context.json` matches scene, PRN, channel, sample rate, project root, raw path, GNSS-SDR path, navigation, trajectory, geometry, and output namespace. No partial/failed marker or empty required file was found.

## Stage Consistency QA

**Stage Consistency = PASS**

| Stage | Observed result |
|---|---:|
| Stage0 valid NAV symbols | 1,292 |
| Stage0 complete 40 ms windows | 1,288 |
| Stage1 scanned windows | 1,288 |
| Stage1 selected windows | 112 |
| Stage2 model evaluations | 448 = 112 windows × 4 model orders |
| Stage2 final L=1/L=2/L=3/L=4 | 45 / 16 / 37 / 14 |
| Stage2 L≥2 / L≥3 | 67 / 51 |
| Stage3 persistence rows | 132 |
| Stage3 reliable centers | 10 |
| Stage4 joint rows | 8 |
| Stage4 joint_valid=1 | 8/8 |
| Stage4 rows with joint_multipath_count>0 | 1 |

The chain is internally consistent: Stage1 is a subset of Stage0 windows; Stage2 evaluates the selected Stage1 windows at all four orders; Stage3 centers derive from the Stage2 candidate set; Stage4 contains eight joint rows for reliable centers. Stage2 L≥2 and Stage3 reliable centers are not counted as confirmed multipath.

## Scientific Validity QA

**Scientific Validity = PASS**

The fixed confirmation criterion was applied:

`joint_valid = 1` AND `joint_multipath_count > 0` AND a matching Stage4 path row has `is_multipath = 1`.

One confirmed event/path satisfies all three conditions:

| Field | Value |
|---|---:|
| Center window | 1264 |
| Time | 60.424560997 s |
| Stage4 joint selected L | 2 |
| joint_valid | 1 |
| joint_multipath_count | 1 |
| Path ID | 2 |
| is_multipath | 1 |
| Delay | 1 sample = 0.1 chip excess delay |
| Doppler | -5642.837162748 Hz |
| Doppler offset | -0.335697905 Hz |
| Relative power | -5.772994698 dB |
| Maximum coherence | 0.899835523 |
| Stage4 minimum multipath power | -5.772994698 dB |

The confirmed path row is unique and finite. No duplicate center/path pair or malformed confirmed row was found. Optional `NaN` values occur only in non-multipath rows where multipath-specific quantities are inapplicable; they are not used as confirmed path parameters. The result supports one task-level confirmed event/path and does not establish a Mountain/Valley or MID statistical law.

## VTC Evidence Impact

- Mountain/Valley evidence: **AVAILABLE** as one independently QA-passed task-level case.
- Special Reflective: **AVAILABLE** through T1-1.
- Highway/Open: **AVAILABLE** through T1-2.
- Urban: existing independently QA-passed production cases remain available.
- T1-3 adds `1 confirmed event / 1 confirmed path` under the fixed Stage4 criterion.

Figure status:

- Figure 2 representative confirmed-path candidate: **AVAILABLE**; T1-3 has a traceable Stage4 path with finite delay, Doppler, power, and coherence evidence.
- Figure 3 hierarchical filtering/confirmation figure: **AVAILABLE**; T1-3 provides complete Stage0–Stage4 funnel evidence.
- Figure 4 environment/elevation comparison: **PARTIAL / CONDITIONAL**; bounded path-level observations are available, but strong event-level LOW/MID/HIGH claims remain blocked by the evidence matrix's `Missing/Partial` window-level TOW geometry join.

## Minimum Evidence Stop Condition

`VTC_MINIMUM_EVIDENCE_STATUS = NOT_SATISFIED`

The required real raw-IQ chain, hierarchical SAGE evidence, confirmed-path examples, valid zero-event/rejection cases, and environment diversity are now represented. However, the current VTC stop condition also requires geometry-QA-complete LOW/MID/HIGH denominators for strong elevation comparisons. The current evidence matrix still records window-level TOW geometry join as `Missing/Partial`. Therefore this QA does not justify a T1-4 request or additional automatic production.

The next minimum route is:

`event/path aggregation -> geometry/time-alignment QA -> figures -> manuscript`

No T1-4 request is created. Further production requires a new Commander decision after the geometry/evidence review.

## Overall Decision

`T1_3_PRODUCTION_QA = PASS`

The task is eligible to be marked `QA_PASS / AVAILABLE` and counted as an accepted 10.23 MHz production task under the project's existing acceptance rules. This report does not claim that Mountain/Valley has no multipath, that MID elevation proves LOS, or that a complete statistical model/database exists.

