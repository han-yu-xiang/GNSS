# Full-Task GPU Candidate Design

**Status:** DESIGN ONLY — awaiting GPT review

**Scope:** Experimental full-task Stage0–Stage4 candidate for two already completed CPU tasks

**Frozen production source:** `scripts/sage_pipeline/run_nav_sage_pipeline.m`
**Authoritative local SHA-256:** `bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c`

```text
FROZEN_SOURCE_EDITED=NO
CANDIDATE_IMPLEMENTED=NO
IMPLEMENTATION_PLAN_CREATED=NO
PRODUCTION_GPU_ENABLED=NO
REMAINING_85_TASK_BATCH_RESUMED=NO
```

## 1. Purpose and success criteria

Build and validate an isolated GPU candidate for the full Frozen SAGE task flow on exactly two existing CPU-complete tasks. The candidate changes only the Stage2 computational implementation and required experimental plumbing. Existing Frozen CPU outputs remain the reference authority; the CPU full task is not rerun.

The validation succeeds only if, for both tasks, Stage0 and Stage1 match the formal outputs exactly; Stage2 has identical evaluated-window, model-validity, selected-order, path-order/identity, and DIRECT/MPC structure; Stage3 persistence and reliable-center structure/classification match; Stage4 joint-result identity and confirmation classification match; and all expected artifacts and schemas are present. Numeric differences are reported as observed, without adding tolerances. Task B does not run unless Task A passes every gate.

This is an experimental validation candidate, not a production architecture. Semantic fidelity takes priority over code deduplication or cleanup.

## 2. Current validated evidence

- The local authority at `E:\GNSS_Multipath_Project\scripts\sage_pipeline\run_nav_sage_pipeline.m` currently has SHA-256 `bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c`.
- The review worktree's existing `scripts/sage_pipeline/run_nav_sage_pipeline.m` has SHA-256 `9a263f8b45c2402b4232f242893cf407f55f0c362e5cbb7369c3bf310b8589f8`. This known review-base mismatch is preserved; it is not replaced or represented as the current authority.
- The 14-window GPU Stage2 qualification is `STRUCTURAL_PASS`: 14/14 CPU-to-formal references passed, 14/14 GPU structural comparisons passed, retry coverage was 7 triggered / 7 not triggered / 0 unknown, and production GPU remains disabled. The qualification summary reports median CPU Stage2 time 39.9017027 s, median warm GPU Stage2 time 8.7940382 s, and median compute-only speedup 4.1157309619×. These are Stage2-only results and are not full-task speedup claims.
- Evidence is in `experiments/sage_gpu/qualification/GPU_STAGE2_QUALIFICATION_SUMMARY.md`, `GPU_STAGE2_QUALIFICATION_RESULTS.csv`, per-window result records, and the run-level historical attestation. No qualification evidence establishes full-task Stage0–Stage4 equivalence.
- Both formal task output directories exist. Their Stage2 selected-path CSVs contain 77 rows for G28/ch1 and 142 rows for G03/ch2. The formal artifacts, not these headline counts, remain the final comparison authority.

## 3. Architecture and data flow

```text
Authoritative local Frozen source (SHA bffc123c…)
        │ copy; production file stays unchanged
        ▼
Experimental candidate in experiments/sage_gpu/full_task_candidate/
        │
        ├── Frozen Stage0
        ├── Frozen Stage1
        ├── qualified GPU Stage2 computation
        ├── Frozen Stage3, consuming candidate Stage2 fits
        └── Frozen Stage4, consuming candidate Stage2 fits and Stage3 centers
                 │
                 └── compare each stage to existing formal Frozen CPU output
```

The candidate is a versioned copy of the authoritative local Frozen source, not a modification of the production file. Candidate-specific entry, project-root/output routing, GPU initialization/data movement, and provenance are isolated as non-scientific plumbing. The review branch's old Frozen file remains untouched.

Alternative approaches were considered. Modifying Frozen production to add a GPU switch is prohibited. An external wrapper that runs Frozen CPU Stage2 and then substitutes files would not make Stage3/Stage4 consume the GPU candidate's in-memory fits and would not validate the requested pipeline. The isolated source copy is therefore the selected approach for this experimental validation.

## 4. Candidate source strategy and helper reuse

```text
COPY_FROM_FROZEN=
E:\GNSS_Multipath_Project\scripts\sage_pipeline\run_nav_sage_pipeline.m

REUSE_EXISTING_GPU_HELPERS=
experiments/sage_gpu/selectSeparatedResidualCandidate.m
qualified GPU Stage2 function bodies in experiments/sage_gpu/stage2_window_173_gpu_probe.m

NEW_CANDIDATE_ONLY_FILES=
experiments/sage_gpu/full_task_candidate/run_nav_sage_pipeline_gpu_candidate.m
```

`selectSeparatedResidualCandidate.m` is directly callable and is used by the qualified GPU residual initializer. The GPU fit and arithmetic routines in `stage2_window_173_gpu_probe.m` are MATLAB file-local functions behind a window-probe entry point that also requires a CPU-fit comparison scratch file. They are not a direct full-task API. The candidate will reuse only the qualified GPU computational function bodies it needs, without copying the probe harness or modifying the existing qualification source. The candidate may keep those functions local to its copied source; a separate helper file is justified only if implementation review shows it is genuinely required.

The qualified GPU implementation includes `fitAllOrdersGpu`, `initializeResidualPathGpu`, `runSageGpu`, `evaluateModelGpu`, `gridSearchPathGpu`, `refinePathGpu`, `scoreReplicaBatchGpu`, `makeReplicaBatchGpu`, `buildReplicasGpu`, `solveAmplitudesGpu`, `synthesizeGpu`, `residualRssGpu`, `replicaCoherenceGpu`, GPU path-state conversion, and CPU gather. Its residual initializer calls the shared `selectSeparatedResidualCandidate` helper.

## 5. Exact Stage2 replacement boundary

The current Frozen source places the Stage1–Stage4 orchestration in `run_sage_stage1_stage4_local` (around line 811). The Stage2 boundary is:

- `runStage2` (around line 1164): owns candidate-window order, checkpoint/resume handling, per-window failure capture, progress saves, and the `fits` collection. This controller remains byte-identical to Frozen and keeps the same `fitAllOrders` call signature.
- `fitAllOrders` (around line 1211): per-window L=1..4 fitting and selected-order result. Its candidate body is limited to Frozen input preparation plus GPU initialization/data movement and a call to the already-qualified `fitAllOrdersGpu` implementation. That qualified model-order loop is reused without tuning or changing its order, validity, or stopping semantics.
- Frozen CPU computational functions around the boundary include `initializeResidualPath` (around line 1281), `runSage` (around line 1314), `evaluateModel` (around line 1354), and their CPU search/refinement/replica/amplitude helpers. The GPU equivalent bodies are the qualified implementations identified above; they are not independently redesigned in this task.
- `flattenStage2` (around line 1415) remains Frozen. It converts the returned fits into the existing model-order, selected-window, and selected-path tables and assigns path IDs and DIRECT/MPC labels.

The candidate must gather GPU values back to CPU double/complex-double values before constructing the fit objects consumed by Frozen `flattenStage2`, Stage3, and Stage4. `runStage2` must retain its existing ordering, checkpoint structure, and per-window error behavior. The candidate must not add a fallback to CPU or silently mark an incomplete GPU fit as valid.

## 6. Stage2 scientific semantics that do not change

The candidate preserves the qualified search and Frozen semantics without new tolerances, rounding, fallbacks, or task-specific rules:

- input window identity and 40 ms observation semantics;
- double precision;
- delay and Doppler grids and their ordering;
- main-path initialization;
- residual-path initialization, candidate ordering, separation rejection/retry, tie handling, and exhaustion behavior;
- path sorting and identity/order;
- SAGE iteration structure, refinement semantics, and stopping rules;
- amplitude solving and complex alpha meaning;
- model validity rules, RSS, and BIC calculations;
- `minimumSequentialBicGain` and `minimumIncrementalRssPercent`;
- selected-L logic;
- DIRECT/MPC labels and Stage2 schemas.

The implementation must not add a PRN-specific or scene-specific scientific branch. GPU initialization, transfer, and gather code are implementation plumbing only.

## 7. Stage0, Stage1, Stage3, and Stage4 preservation

Stage0, Stage1, Stage3, and Stage4 are not GPU-enabled or scientifically modified. Their implementation bodies are copied from the authoritative Frozen source. Any candidate entry/path change is separately classified as `NON_SCIENTIFIC_PLUMBING_DIFF`.

Stage3's `evaluatePersistence(fits, windows, cfg)` consumes the in-memory Stage2 fits. It reads selected-order paths and relative powers, looks up neighboring fits by window ID, and applies the existing persistence comparisons. It does not consume the Stage2 CSVs as its computational input.

Stage4's `runJointStage(reliable, fits, symbols, windows, rawFile, dopplerSign, cfg)` consumes Stage3 reliable centers and the in-memory Stage2 fits for every model order. It uses those paths as seeds for joint optimization and then applies the existing joint selection and confirmation rules. Consequently, candidate fit IDs, per-order validity/path structures, CPU-gathered values, and Stage3 center mappings must remain available and consistent.

## 8. Stage2 output contract and downstream dependencies

The Frozen orchestration writes and saves the following Stage2 artifacts:

| Artifact | Frozen producer/content | Downstream role |
|---|---|---|
| `stage2_model_orders.csv` | `flattenStage2`; one row per evaluated window and L=1..4 | QA/comparison and public Stage2 result |
| `stage2_selected_windows.csv` | `flattenStage2`; selected order and selected-model metrics per fitted window | QA/comparison and public Stage2 result |
| `stage2_selected_paths.csv` | `flattenStage2`; selected paths in path order | QA/comparison and public Stage2 result |
| `stage2_nav_progress.mat` | `runStage2` checkpoint: `fits`, `completed`, `candidateIndices`, and `cfg` | Resume/checkpoint state only; candidate execution still uses `Resume=false` |
| `stage2_nav_sage_L1_L4.mat` | final `stage2Fits`, the three flattened tables, and `cfg` | serialized Stage2 result; Stage3/Stage4 consume `stage2Fits` during the pipeline run |

The required Stage0–Stage4 artifact set is `stage0_nav_catalog.mat`, `stage0_valid_symbols.csv`, `stage0_valid_40ms_windows.csv`, `doppler_sign.mat`, `stage1_nav_fast_scan.csv`, `stage1_nav_fast_scan.mat`, `stage1_nav_progress.mat`, the five Stage2 artifacts above, `stage3_nav_persistence.mat`, `stage3_persistence.csv`, `stage3_reliable_centers.csv`, `stage4_nav_joint_100ms.mat`, `stage4_joint_summary.csv`, and `stage4_joint_paths.csv`. Candidate `run_context` and overview output are checked as run metadata/diagnostic artifacts. This contract does not include post-pipeline CIR/HDF5 or alpha sidecars that exist beside the formal G28 reference; the candidate must not create or require those sidecars.

The exact CSV column order is:

```text
stage2_model_orders.csv:
window_id,recording_time_s,model_order,multipath_count,rss,bic,
bic_gain_from_previous,rss_gain_percent_from_previous,model_valid,selected,
minimum_multipath_power_db,minimum_separation_samples,
maximum_relative_doppler_hz,maximum_coherence

stage2_selected_windows.csv:
window_id,recording_time_s,tow_s,selected_L,multipath_count,selected_bic,
selected_rss,minimum_multipath_power_db,maximum_relative_doppler_hz,
maximum_coherence

stage2_selected_paths.csv:
window_id,recording_time_s,selected_L,path_id,is_multipath,delay_samples,
excess_delay_samples,excess_delay_chips,excess_path_length_m,doppler_hz,
doppler_offset_hz,relative_power_db
```

The schemas are generated by the Frozen `emptyModelRecord`, `emptySelectedRecord`, `emptyPathRecord`, `struct2table`, and `writetable` code and must keep this exact order. In MATLAB, `model_valid`, `selected`, and `is_multipath` are logical; numeric estimates and identifiers are double. `model_order` and `selected_L` are total path count L; `multipath_count=L-1`; `path_id` is the delay-sorted ordinal; path 1 is the direct reference and later paths are MPCs. `rss` is the model residual sum of squares and `bic` is the existing model-selection quantity. Sequential BIC gain is previous BIC minus current BIC; RSS gain percentage uses the previous RSS and the Frozen denominator. `delay_samples` is absolute path delay; excess delay is relative to path 1; excess chips and path length are derived from that excess delay. `doppler_hz` is the path Doppler and `doppler_offset_hz` is relative to path 1. Relative power is normalized to path 1. Minimum multipath power, minimum separation, maximum relative Doppler, and maximum coherence retain the Frozen model diagnostics. The fit contract includes window identity, selected order, and L=1..4 model structs; each model carries validity, RSS/BIC, relative powers, diagnostics, and ordered paths with delay, Doppler, complex alpha, and score. No Stage3/4 implementation should infer fits by reparsing a partial CSV.

## 9. Candidate output namespace and execution order

The only candidate output destinations are:

```text
scenes/F1023_V70_D0117_P2/sage_results/gpu_candidate_fulltask_20261005/G28_ch1
scenes/F1023_V120_D0121_P2/sage_results/gpu_candidate_fulltask_20261005/G03_ch2
```

Each run uses `Resume=false`. Before creating any output, the candidate must fail closed if its exact destination already exists. It must never write to `rerun_20261003_frozen_v3`, reuse or overwrite a prior candidate result, or resume a checkpoint.

Task A runs first: `F1023_V70_D0117_P2 / G28 / ch1`, compared with `scenes/F1023_V70_D0117_P2/sage_results/rerun_20261003_frozen_v3/G28_ch1`. Task B is `F1023_V120_D0121_P2 / G03 / ch2`, compared with `scenes/F1023_V120_D0121_P2/sage_results/rerun_20261003_frozen_v3/G03_ch2`; it may start only after Task A passes all stages.

The known formal counts are sanity checks, not substitutes for reading the reference files: G28/ch1 has 900 valid symbols / 898 Stage0 windows, 898 Stage1 scans / 54 selected windows, 54 Stage2 fits / 77 selected paths (54 direct, 23 MPC), 23 Stage3 persistence rows / 2 reliable centers, and 2 Stage4 joint rows. G03/ch2 has 232 valid symbols / 230 Stage0 windows, 230 Stage1 scans, 96 Stage2 fits / 142 selected paths (96 direct, 46 MPC), 46 Stage3 persistence rows / 9 persistent MPC, and 8 Stage4 joint rows. Actual formal artifacts remain authoritative.

## 10. Per-stage comparison policy

**Stage0 — exact.** Compare required artifact presence, CSV headers/order, row counts, window/symbol identities, timing/sample indices, NAV symbols, tracking/code-frequency fields, and every exported value. Any difference fails the task.

**Stage1 — exact.** Compare artifact presence, headers/order, scan/selected window identity, main delay/Doppler/score, and every exported value. Any difference fails the task.

**Stage2 — structural equivalence plus raw numeric reporting.** Compare evaluated-window identity/count, model-order row count, selected-window row count, selected-path row count, direct-path/MPC counts, all L=1..4 validity values, selected L, selected path count, order/identity, and DIRECT/MPC labels. Record maximum absolute and relative numeric differences for delay, Doppler, relative power, complex alpha, path score, RSS, and BIC. Do not introduce a numeric tolerance or claim bitwise equality.

For every evaluated window, also record formal CPU and candidate GPU best L, second-best L, and BIC margin (`BIC(second-best) - BIC(best)` over valid models). Report the minimum margin and its window on each side. This is diagnostic only and does not change model selection.

**Stage3 — structural/classification equivalence.** Compare persistence row count and keys, path/window mapping, every persistence decision and status/classification field, reliable-center identities/count, and exported schema/order. Record numeric differences separately where applicable.

**Stage4 — structural/classification equivalence.** Compare joint-result/snapshot counts, center and path mapping, selected model order, validity, confirmed/not-confirmed classification, and exported schema/order. Record numeric fields separately where applicable. Require explicit matches for `STAGE4_RESULT_IDENTITY_MATCH` and `STAGE4_CONFIRMATION_CLASSIFICATION_MATCH`.

For each stage, verify the expected artifact set and CSV schema. MAT files are checked for required presence and semantic contents, not binary hash identity. A candidate may pass only if its artifact set and downstream semantics match the formal result.

Performance evidence records each task's candidate wall time, GPU initialization, Stage2 GPU time, and Stage2 transfer-in/gather time where separately measurable. Compare against historical formal CPU full-task runtime only when a trustworthy same-scope measurement exists; otherwise report `FULL_TASK_SPEEDUP=NOT_COMPARABLE`. Do not extrapolate the 14-window Stage2 timings into a full-task speedup.

## 11. Fail-closed behavior and overall status

- A frozen-source hash mismatch, candidate source/provenance inconsistency, unexpected semantic diff, active conflicting runner/lock, output collision, or GPU initialization failure blocks execution before task work.
- Any Task A mismatch yields `TASK_A_FULL_VALIDATION=FAIL` and `TASK_B=NOT_RUN`.
- Task B starts only after the entire Task A comparison passes. Any Task B mismatch stops validation. No automatic candidate patch-and-continue is allowed.
- `FULL_TASK_GPU_CANDIDATE_VALIDATION=PASS_2_OF_2` requires both tasks to pass Stage0 exact, Stage1 exact, Stage2 structural, Stage3 structural/classification, Stage4 structural/classification, and artifact/schema checks.
- A mismatch remains a failure/blocker with its original outputs and evidence preserved. Any candidate repair requires a separately reviewed phase.

## 12. Provenance and semantic diff audit

Each task execution record will bind:

```text
frozen_source_sha256
gpu_candidate_source_sha256
qualified_gpu_stage2_source_identity
execution_timestamp
scene_id / PRN / tracking_channel
Resume=false
reference_output_namespace
candidate_output_namespace
```

Before execution, produce a source diff audit against the exact local Frozen source and classify every difference as exactly one of:

1. `GPU_STAGE2_COMPUTATIONAL_DIFFERENCE` — the qualified GPU Stage2 computation and required data movement;
2. `NON_SCIENTIFIC_PLUMBING_DIFF` — candidate entry, explicit project/output routing, fail-closed namespace check, and GPU initialization;
3. `PROVENANCE_INSTRUMENTATION` — candidate-only identity and run metadata.

Any unclassified difference is `UNEXPECTED_DIFF` and blocks execution. The Frozen production source remains unchanged before and after execution.

## 13. Minimal testing strategy

Tests are limited to the new candidate boundary:

- verify the authoritative Frozen SHA before/after and verify no production-path edit is present;
- verify the two task identities resolve to their declared scene/PRN/channel and formal reference paths;
- verify an existing candidate destination fails closed and cannot be resumed or overwritten;
- verify the candidate Stage2 dispatch returns the fit structure required by Frozen flattening and Stage3/Stage4;
- verify the comparison validator detects mismatched schemas, row/order/identity/classification fields and reports raw numeric deltas without tolerances.

The principal scientific validation remains the two real full-task regressions. No large new unit-test framework or reimplementation of Frozen algorithm tests is in scope.

## 14. Files expected in a later implementation/validation phase

The following are future deliverables only; none are created by this design-spec phase:

- `experiments/sage_gpu/full_task_candidate/run_nav_sage_pipeline_gpu_candidate.m` — copied Frozen pipeline with only the reviewed Stage2 substitution and candidate plumbing;
- a minimal candidate invocation/comparison driver and its boundary tests under `experiments/sage_gpu/full_task_validation/`;
- lightweight `FULL_TASK_GPU_VALIDATION_SUMMARY.md`, `FULL_TASK_GPU_VALIDATION_RESULTS.csv`, and a per-window Stage2 comparison CSV under `experiments/sage_gpu/full_task_validation/`;
- an additive Engineering Handoff entry only after a final pass or a clearly classified blocker.

The review bundle may include the candidate source, minimal tests, and lightweight evidence. It must exclude raw IQ, MAT/HDF5 outputs, full candidate result trees, archives, and large profiler artifacts. Paper Handoff is not changed.

## 15. Explicit non-goals

- Modify or replace Frozen production, or enable production GPU;
- rerun either CPU full-task reference;
- start any task other than G28/ch1 then conditionally G03/ch2;
- resume the remaining 85-task CPU batch or run 20.46 MHz;
- run CIR, alpha export, local/global ledger, channel modeling, or paper analysis;
- alter thresholds, grids, model-order rules, semantics, or historical results;
- publish raw IQ, MAT/HDF5, archives, or full result trees;
- change the Paper Handoff or claim general GPU production qualification from two tasks.

## 16. Risks and known limitations

- GPU floating-point differences can alter a model-validity, selection, persistence, or joint-confirmation boundary. No tolerance may hide such a change; any structural/classification mismatch stops the sequence.
- The existing qualified GPU routines are local to a window-probe MATLAB file and coupled to its scratch/comparison harness. Only their needed qualified computational bodies can be reused in the candidate; integration must preserve their source identity and behavior.
- Stage3 and Stage4 amplify the importance of complete candidate Stage2 in-memory structures; matching only Stage2 CSV row counts is insufficient.
- The two tasks cover two scenes and selected PRN/channels only. A pass does not qualify the other 85 tasks, 20.46 MHz, or production GPU operation.
- Historical full-task CPU runtime is comparable only if a trustworthy same-scope measurement exists; otherwise report `FULL_TASK_SPEEDUP=NOT_COMPARABLE`. Stage2 qualification timing must not be extrapolated to full-task speedup.

## 17. Design-phase boundary

This document records an approved architecture direction for GPT review. At this phase, the candidate and validators are not implemented; no implementation plan is written; no MATLAB/GPU run or raw-IQ read is authorized. Production GPU remains disabled, the Frozen CPU source is unmodified, the remaining 85-task batch remains paused, the Paper Handoff remains unchanged, and the business branch receives no commit or push.

