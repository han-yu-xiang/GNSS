# Full-Task GPU Candidate — Validator Review Fixes

STATUS SNAPSHOT ONLY. This is lightweight implementation/review evidence, not an experiment result or a replacement for either project handoff.

```ini
IMPLEMENTATION_TASKS=1-4
VALIDATOR_REVIEW_FIXES=COMPLETED
TASK_A=NOT_RUN
TASK_B=NOT_RUN
TASK_A_PREFLIGHT_RUN=NO
RAW_IQ_READ=NO
SAGE_EXECUTED=NO
FORMAL_CANDIDATE_NAMESPACE_CREATED=NO
REMAINING_85_TASK_BATCH_RESUMED=NO
FULL_TASK_SPEEDUP=NOT_COMPARABLE
```

## Source authority and boundary

```ini
FROZEN_AUTHORITY=E:/GNSS_Multipath_Project/scripts/sage_pipeline/run_nav_sage_pipeline.m
FROZEN_AUTHORITY_SHA256=bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c
FROZEN_PRODUCTION_MODIFIED=NO
CANDIDATE_INITIAL_COPY_SHA256=bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c
CANDIDATE_SOURCE_SHA256=1816f57f2cd199d1092fa9d30e194d2b4b42818a228280fb096c77b9eafc40fb
QUALIFIED_GPU_PROBE_SHA256=bfe56ad02c99240257fddd212ba43ee5606a81740b3dda716c5947c433cbfa88
QUALIFIED_SELECTOR_SHA256=a40c6459e66a384e85053589b270c5d2e112363872153fbf46da5c56fd4bb1f5
```

The review branch's pre-existing `scripts/sage_pipeline/run_nav_sage_pipeline.m` remains at SHA-256 `9a263f8b45c2402b4232f242893cf407f55f0c362e5cbb7369c3bf310b8589f8`. It is preserved review-base content, not the Frozen execution authority; the experimental candidate was copied from the absolute local `bffc...` authority above.

`FULL_TASK_GPU_SOURCE_DIFF_AUDIT.csv` was generated against that local authority. Result: 99 function rows; 68 unchanged; 18 allowed `GPU_STAGE2_COMPUTATIONAL_DIFFERENCE` rows (the `fitAllOrders` replacement plus 17 normalized-exact qualified helper bodies); 11 allowed `NON_SCIENTIFIC_PLUMBING_DIFF`; 2 allowed `PROVENANCE_INSTRUMENTATION`; `UNEXPECTED_DIFF=0`.

The audit confirms `runStage2`, `flattenStage2`, `evaluatePersistence`, and `runJointStage` byte-identical to Frozen. The Frozen `fitAllOrders(row, scanRow, rawFile, dopplerSign, cfg)` signature is retained. The complete fit is gathered and recursively checked for CPU residency before return. The candidate entry initializes one GPU device per task; candidate provenance is stored separately from `cfg`. Candidate Stage0–Stage4 execution was not performed.

## Verification receipts

```ini
Pester=19_PASS_0_FAIL
MATLAB_COMPARISON_TESTS=15_PASS
MATLAB_FIT_CONTRACT_TESTS=4_PASS
MATLAB_TOTAL_SYNTHETIC_TESTS=19_PASS_0_FAIL
MATLAB_FUNCTION_RESOLUTION=PASS
MATLAB_STARTUP_AND_ARGUMENTLIST_SMOKES=PASS
GIT_DIFF_CHECK=PASS
```

MATLAB was used only for startup/argument transport and synthetic unit fixtures, including the CPU-resident fit contract. No formal task, raw IQ, candidate SAGE Stage, or production namespace was accessed or created.

Final review found and fixed a validator gap: Stage2–Stage4 CSV numeric cells are now checked against each side's MAT table by exact parsed-cell comparison to a same-writer temporary CSV round-trip. No numeric tolerance was added. A synthetic CSV-only delay mutation was observed to fail before the fix and pass its expected fail-closed assertion after the fix.

No `FULL_TASK_GPU_VALIDATION_RESULTS.csv` or `FULL_TASK_GPU_STAGE2_WINDOW_COMPARISON.csv` rows are included because no real task comparison has run; no placeholder rows were created.

## GPT implementation-review corrections

```ini
EVIDENCE_PERSISTENCE=IMPLEMENTED_AND_SYNTHETICALLY_TESTED
RESULTS_CSV_TASK_APPEND=PASS
WINDOW_CSV_PER_EVALUATED_WINDOW=PASS
DUPLICATE_TASK_KEY=FAIL_CLOSED
FAILURE_TERMINAL_RECEIPT=IMPLEMENTED
SEQUENTIAL_SELECTION_REPLAY=IMPLEMENTED_AND_SYNTHETICALLY_TESTED
GLOBAL_BIC_BEST_SECOND_MARGIN=REMOVED
CPU_SELECTION_REPLAY=REQUIRED_TO_MATCH_FORMAL_SELECTED_ORDER
GPU_SELECTION_REPLAY=REQUIRED_TO_MATCH_CANDIDATE_SELECTED_ORDER
TASK_A_EXECUTION=NOT_AUTHORIZED
TASK_B_EXECUTION=NOT_AUTHORIZED
```

Successful comparisons now persist a task-level row and one Stage2 comparison row per evaluated window under this `full_task_validation` directory. Task B appends without dropping Task A; an existing `(task, scene, PRN, channel)` evidence key blocks rather than overwriting. Candidate/comparison failures produce a lightweight terminal row and refresh this summary. No scientific output tree is used as an evidence destination.

Sequential diagnostics replay the Frozen order-by-order decision using `maximumModelOrder`, `minimumSequentialBicGain`, and `minimumIncrementalRssPercent` from each saved Stage2 `cfg`. Each checked transition records BIC/RSS gain, threshold, threshold surplus, model validity, and accepted/rejected status. Later transitions after the first rejection remain unchecked (`NaN` numeric diagnostics). No global best-vs-second-best BIC margin is reported.

One earlier MATLAB startup smoke printed its marker but exited with code 3. No workaround was made. Subsequent startup/ArgumentList/function-resolution smokes and the complete synthetic test run passed. The Task A preflight must repeat startup smoke; any nonzero exit blocks before candidate execution or raw-IQ access.

```ini
ENGINEERING_HANDOFF_MODIFIED=NO
PAPER_HANDOFF_MODIFIED=NO
20_46_MHZ_EXECUTED=NO
BUSINESS_BRANCH_COMMIT_PUSH=NO
FROZEN_PRODUCTION_MODIFIED=NO
CANDIDATE_SOURCE_MODIFIED=NO
NEXT_STEP=GPT_REVIEW_VALIDATOR_FIXES
```
