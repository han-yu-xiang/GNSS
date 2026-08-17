# Batch-sampled-v1.2 raw-coarse prototype report

## Verdict

**FAIL — do not run G11 and do not design or request a sampled SAGE pilot from this prototype.**

The Phase-A evaluator completed its frozen G16 production pass but did not complete the required G25 control pass: the G25 process stopped making observable progress overnight and was terminated while preserving all existing artifacts.  More importantly, every G16 profile promoted the entire 2,229-window catalog as one component and the shared raw-coarse pass took 18,806.16 s (5.22 h), 4.82 times the historical 3,900 s (65 min) full Stage1 baseline.  That fails the engineering-cost gate independently of any coverage result.

The partial execution also exposed a profile-construction defect: the frozen `coarse_parameter.json` labelled profiles `D100` and `D200`, but its actual offsets were `(-1,0,+1)` Hz.  The evaluator has been corrected so future profile construction derives `(-100,0,+100)` and `(-200,0,+200)` Hz respectively; the completed G16 pass is retained as an interrupted, pre-fix diagnostic artifact and is **not** a valid D100/D200 performance result.

## Scope and safety record

- Planner/evaluator: `scripts/sage_pipeline/run_batch_sampling_raw_coarse_v1_2.py`.
- Phase A frozen before any Stage1–Stage4/gold read, hash `3439e193ffefdfaddac39b354719ca300a939d5c1cfeddcda2e1eda411be76c0`.
- Raw input was parsed read-only from each scene `metadata.json`; MATLAB and SAGE were never called.
- No `stage1_nav_fast_scan.csv` was written and no file under any `sage_results` directory was changed.
- All artifacts are confined to `dataset_generation_logs/sampling_validation/batch_sampled_v1_2_prototype/`.
- Interruption record: `dataset_generation_logs/sampling_validation/batch_sampled_v1_2_prototype/phase_a_interruption.json`.

## Frozen Phase-A profiles

| Profile | Intended subblocks | Intended tracking-centred offsets | C1 rule |
|---|---:|---:|---|
| B1_20msx2_D100 | 20 ms × 2 | -100, 0, +100 Hz | high/low hysteresis, bridge 2, boundary +2, closure ±2 |
| B2_10msx4_D100 | 10 ms × 4 | -100, 0, +100 Hz | same |
| B2_10msx4_D200 | 10 ms × 4 | -200, 0, +200 Hz | same |

The stored pre-fix manifest instead records `-1,0,+1` Hz for all three.  The code fix is unit-tested but was not used to rerun raw IQ in this report; it must receive a new parameter hash and new output namespace for a future Phase-A attempt.

## G16 partial Phase-A result

Task: `F1023_V70_D0120_P7/G16/ch1`, 10.23 MHz, Stage0 N0 = 2,229.

| Profile | Promoted windows | Promotion fraction | Components | Potential fine windows | G16 confirmed centers | Confirmed ±2 closure | Stage3 reliable-center ±2 closure |
|---|---:|---:|---:|---:|---:|---:|---:|
| B1_20msx2_D100 | 2,229 | 100% | 1 | 2,229 | 4/4 (100%) | 4/4 (100%) | 11/11 (100%) |
| B2_10msx4_D100 | 2,229 | 100% | 1 | 2,229 | 4/4 (100%) | 11/11 (100%) |
| B2_10msx4_D200 | 2,229 | 100% | 1 | 2,229 | 4/4 (100%) | 11/11 (100%) |

The four post-freeze gold confirmed centers are 1337, 1338, 1406, and 2079.  The apparent 100% coverage is non-discriminative: all Stage0 windows were made fine-available.  It is not evidence that the coarse score finds multipath efficiently, nor does it constitute a multipath label for any promoted window.

## Measured G16 cost

The B1/B2 profiles shared one raw pass; the following values therefore apply to all three profiles.

| Measure | Value |
|---|---:|
| Contiguous raw chunks / actual opens | 28 / 28 |
| Theoretical per-window opens | 2,229 |
| Actual raw bytes read | 1,847,132,692 bytes |
| Theoretical independent-window read | 3,648,427,200 bytes |
| Read reduction | 49.37% |
| Wall-clock | 18,806.16 s (5.22 h) |
| CPU time | 3,147.70 s |
| Average wall-clock per window | 8.437 s |
| Peak traced memory | 141,908,165 bytes |
| Historical G16 full Stage1 wall-clock | 3,900 s (65 min) |
| Coarse/full-Stage1 wall ratio | 4.822× |

The contiguous-chunk I/O design demonstrably reduces reopen/read volume, but the standard-library per-sample correlation implementation is not computationally viable.  The all-window C1 component also means projected fine work remains N0=2,229; F1200 is `budget_exhausted_inconclusive`.

## G25 control and G11 gate

`F1023_v50_D0127_P1/G25/ch0` began Phase A with its metadata/raw input receipt but produced no profile manifests, cost record, promotion record, or coverage replay before it stopped progressing.  Therefore G25 control promotion fraction and cost are **not measured**.  They must not be inferred from G16.

The Phase-B task `F1023_V120_D0121_P2/G11/ch0` was never started.  It is disallowed because Phase A is incomplete and G16 fails the frozen cost gate.  No G11 raw IQ was read by this prototype.

## Test and implementation record

`python -m py_compile` and `python -m unittest scripts.sage_pipeline.test_run_batch_sampling_raw_coarse_v1_2 -v` passed after the Doppler-grid correction: 9 tests passed.  Coverage includes IQ layout/sample offsets, NAV wipe, chunk overlap reuse, 10/20 ms slicing, deterministic score calculation, C1 component merge, budget/inconclusive handling, parameter hash/gold-leakage guard, and the actual D100/D200 grid derivation.

## Sole next action

Redesign the coarse computation before any new Phase-A run: preserve the independent, frozen selection/gold-replay protocol, but replace the standard-library per-sample correlation loop with a vectorized or compiled chunk-level implementation and validate raw-I/O progress/timeout handling.  Then create a fresh parameter hash/output namespace and rerun the complete G16+G25 Phase A using the corrected true ±100/±200 Hz grids.  Do **not** tune against gold event windows, run G11, resume Wave-2A full scan, or issue a sampled SAGE request first.
