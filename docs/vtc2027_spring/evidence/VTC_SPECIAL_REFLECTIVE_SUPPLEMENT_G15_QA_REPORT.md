# VTC Special Reflective Supplement QA & Paper Decision Report

Date: 2026-08-17

Task: `F1023_V70_D0122_P2/G15/ch8/10.23MHz`

## Execution integrity

| Check | Result | Evidence |
|---|---|---|
| Request path | PASS | `dataset_generation_logs/batch_sage_execution_requests/vtc_special_reflective_supplement_p2_g15_20260817/execution_request.json` |
| Request SHA match | PASS | Request and receipt both `0d8de5948101f67bfc9458785d40f876412617b2fd903d695aab2cb85abd85a5` |
| Request scope | PASS | Scene `F1023_V70_D0122_P2`, PRN `G15`, channel `8`, sample rate `10230000 Hz` |
| `new_only` | PASS | `true` in immutable request |
| `resume_allowed` | PASS | `false` in immutable request |
| Actual MATLAB Resume value | PASS | Command preview and task log both contain `'Resume', false`; no `'Resume', true` occurrence |
| Windows identity | PASS | `TJ-CHANNEL\Jing_` |
| MATLAB smoke | PASS | marker `MATLAB_STARTUP_OK`, exit code `0` |
| Python executor exit | PASS | exit code `0` |
| Task exit | PASS | exit code `0` |
| Task status | PASS | `completed` in execution receipt and status history |
| Output namespace | PASS | `scenes/F1023_V70_D0122_P2/sage_results/nav_sage_v2/G15` |

Execution artifacts:

- Environment receipt: `dataset_generation_logs/batch_sage_execution/windows_runner_receipts/vtc_special_reflective_supplement_p2_g15_20260817_20260816T164637801Z/environment_receipt.json`
- Execution receipt: `dataset_generation_logs/batch_sage_execution/windows_runner_receipts/vtc_special_reflective_supplement_p2_g15_20260817_20260816T164637801Z/execution_receipt.json`
- Execution log: `dataset_generation_logs/batch_sage_execution/batch_sage_execution_20260816T164900Z/batch_execution_log.csv`
- Status history: `dataset_generation_logs/batch_sage_execution/batch_sage_execution_20260816T164900Z/status_history.jsonl`
- Task log: `dataset_generation_logs/batch_sage_execution/batch_sage_execution_20260816T164900Z/task_logs/F1023_V70_D0122_P2__G15__ch8__nav_sage_v2.log`

Runtime was `7711.011 s` (Python receipt duration `7711.209 s`). The execution was a single-task normal-user wrapper run; no second task was started.

## Artifact completeness

The output directory contains exactly 21 expected files, all non-empty:

```text
doppler_sign.mat
G15_nav_sage_overview.png
run_context.json
run_context.mat
stage0_nav_catalog.mat
stage0_valid_40ms_windows.csv
stage0_valid_symbols.csv
stage1_nav_fast_scan.csv
stage1_nav_fast_scan.mat
stage1_nav_progress.mat
stage2_model_orders.csv
stage2_nav_progress.mat
stage2_nav_sage_L1_L4.mat
stage2_selected_paths.csv
stage2_selected_windows.csv
stage3_nav_persistence.mat
stage3_persistence.csv
stage3_reliable_centers.csv
stage4_joint_paths.csv
stage4_joint_summary.csv
stage4_nav_joint_100ms.mat
```

`run_context.json` agrees with scene `F1023_V70_D0122_P2`, PRN `G15`, tracking channel `8`, sampling rate `10230000 Hz`, and the request output namespace. No partial, failed, or abort marker was found in the execution receipt, status history, task log, or output directory. The expected missing-value tokens in non-confirmed rows are documented below; they are not treated as confirmed-path corruption.

`ARTIFACT_COMPLETENESS = PASS`

## Pipeline result and Stage consistency

| Stage | Result |
|---|---:|
| Stage0 valid NAV symbols | 3695 |
| Stage0 complete 40 ms windows | 3687 |
| Stage1 scanned windows | 3687 |
| Stage1 selected/candidate windows | 108 |
| Stage2 model evaluations | 432 |
| Stage2 final selected windows | 108 |
| Stage2 L1/L2/L3/L4 selected windows | 42 / 33 / 10 / 23 |
| Stage2 L≥2 / L≥3 | 66 / 33 |
| Stage3 persistence rows | 122 |
| Stage3 reliable centers | 10 |
| Stage4 joint rows | 8 |
| Stage4 `joint_valid=1` rows | 8 |
| Confirmed events | 5 |
| Confirmed multipath paths | 5 |

The chain is consistent: Stage1 scanned all Stage0 windows; Stage2 evaluated four model orders for each of 108 selected windows; Stage3 produced 10 reliable centers; Stage4 operated on 8 joint rows. Stage2 higher-order selections and Stage3 reliable centers are intermediate evidence only.

`STAGE_CONSISTENCY = PASS`

## Confirmed-path criterion and parameters

The fixed criterion was applied without modification:

```text
joint_valid == 1
AND joint_multipath_count > 0
AND matching stage4_joint_paths.is_multipath == 1
```

The five confirmed paths are:

| Window | Time (s) | Path | Excess delay (samples) | Excess delay (chips) | Signed relative Doppler (Hz) | Absolute relative Doppler (Hz) | Relative power (dB) | Coherence |
|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 1079 | 48.1851454545455 | 2 | 1.4 | 0.14 | 31.5397446616225 | 31.5397446616225 | -1.80956213069539 | Path-level field not stored; joint maximum coherence 0.397762165828743 |
| 2167 | 88.0253566959922 | 2 | 1.2 | 0.12 | -31.5908908130405 | 31.5908908130405 | -15.915910929625 | Path-level field not stored; joint maximum coherence 0.406477252560228 |
| 1080 | 48.2051455522972 | 2 | 1.2 | 0.12 | 32.669775811979 | 32.669775811979 | -0.894023466898675 | Path-level field not stored; joint maximum coherence 0.380448863755352 |
| 1081 | 48.2251456500489 | 2 | 1.7 | 0.17 | 33.7998069590485 | 33.7998069590485 | -6.46223617047156 | Path-level field not stored; joint maximum coherence 0.334191709120472 |
| 2166 | 88.0053565982405 | 2 | 1.5 | 0.15 | 38.7713679767876 | 38.7713679767876 | -17.2994359360271 | Path-level field not stored; joint maximum coherence 0.226366981147705 |

The Stage4 path table contains no path-specific coherence column. The joint-summary `maximum_coherence` values are therefore reported as a separate event/joint diagnostic and are not substituted for path-level coherence. Confirmed delay, Doppler, and relative-power fields are finite and unique by window/path. The expected `NaN` values in Stage0 fallback speed fields, non-selected model-order fields, and Stage4 zero-multipath rows do not occur in the confirmed path parameters.

`SCIENTIFIC_PATH_FIELD_SANITY = PASS_WITH_COHERENCE_PROVENANCE_LIMITATION`

## Updated Special Reflective evidence

The original QA-passed `F1023_V70_D0120_P9/G05/ch10` case and this independent G15 case yield:

```text
N_SCENES = 2
N_TASKS = 2
N_EVENTS = 7
N_PATHS = 7
```

Combined path-parameter summary across the two scenes:

| Parameter | n available | Missing | Median | Min | Max | IQR |
|---|---:|---:|---:|---:|---:|---:|
| Excess delay (samples) | 7 | 0 | 1.2 | 1.1 | 1.7 | 0.25 |
| Relative power (dB) | 7 | 0 | -6.46223617047156 | -17.2994359360271 | -0.894023466898675 | 9.21201328566292 |
| Signed relative Doppler (Hz) | 7 | 0 | 31.5397446616225 | -31.5908908130405 | 38.7713679767876 | 21.403718531235853 |
| Absolute relative Doppler (Hz) | 7 | 0 | 31.5908908130405 | 11.7153663155214 | 38.7713679767876 | 11.491529358185304 |
| Path-level coherence | 2 | 5 | 0.801019299621328 | 0.793658893110847 | 0.808379706131809 | 0.007360406510480977 |

The coherence summary is explicitly partial: the two original G05 path rows contain coherence, while the five new G15 Stage4 path rows do not. No event-level elevation value was assigned; the existing NMEA/GSV geometry alignment remains partial and the new task is represented by its scene-level environment label only.

## QA decision

`SCIENTIFIC_QA = PASS`

The output is complete, the request and execution contract match, all required Stage0–Stage4 links are present, and the five confirmed paths satisfy the fixed Stage4 criterion. The path-level coherence limitation is retained as provenance and does not alter the confirmation result.

## Paper decision

`SPECIAL_REFLECTIVE_PAPER_DECISION = KEEP_IN_MAIN_ENVIRONMENT_COMPARISON`

Decision basis:

- two independent Special Reflective scenes are now represented;
- both tasks use the same 10.23 MHz production estimator and final confirmation semantics;
- the second scene adds five independently QA-passed confirmed path rows with delay, signed/absolute relative Doppler, and relative-power values;
- the evidence is sufficient for a bounded descriptive environment comparison, while remaining too small for a statistical distribution, occurrence probability, or elevation-conditioned conclusion;
- the decision is based on replication, usable path evidence, and comparability—not on whether the values follow an expected trend or improve a figure.

This decision does not mean that Special Reflective is statistically characterized or that all scenes are complete. The partial window-level geometry/time alignment remains a limitation.

## Next paper impact (proposal only)

- Figure 4: retain the four-environment descriptive structure, add the five new G15 path points, and show the updated Special Reflective sample size `n=7`; do not redraw in this QA task.
- Table II: retain Special Reflective as a bounded environment group and report path sample size/provenance; do not add event-level elevation claims.
- Results: include Special Reflective as a replicated but small path-level environment case; keep all statements descriptive and avoid fitted statistical models or causal environmental conclusions.

## Final

```text
AUTO_CONTINUATION = NO
NEW_SECOND_TASK_EXECUTED = NO
HIGHWAY_EXECUTED = NO
URBAN_EXECUTED = NO
MOUNTAIN_VALLEY_EXECUTED = NO
NEXT_VTC_DECISION_REQUIRED = YES
```

No additional production request was generated. Existing SAGE outputs, request, manifest, metadata, inventory, and pipeline code were not modified by this QA task.
