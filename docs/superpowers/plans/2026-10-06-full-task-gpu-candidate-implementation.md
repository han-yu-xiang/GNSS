# Full-Task GPU Candidate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an isolated full-task GPU candidate and validate it against the two existing Frozen CPU task outputs, with a mandatory GPT review stop after Task A and separate authorization before Task B.

**Architecture:** Copy the authoritative local Frozen pipeline into one experimental candidate and replace only the per-window Stage2 computation with already-qualified GPU function bodies. Preserve the Frozen runStage2 controller and fitAllOrders signature, gather the complete fit to CPU before returning, and run one task per invocation through a PowerShell 7 driver plus an independent MATLAB comparison validator.

**Tech Stack:** MATLAB, PowerShell 7, .NET ProcessStartInfo.ArgumentList, Pester, MATLAB Unit Test, Git.

**Spec:** `docs/superpowers/specs/2026-10-05-full-task-gpu-candidate-design.md`

## Global Constraints

- This plan is not implementation or execution authorization. Candidate code, MATLAB/GPU execution, and raw-IQ reads require the later review/authorization gates described below.
- The only Frozen authority is E:/GNSS_Multipath_Project/scripts/sage_pipeline/run_nav_sage_pipeline.m, SHA-256 bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c. Never copy the review branch's old 9a263f... Frozen file.
- Recompute the qualified GPU source hashes before implementation; current reference identities are listed in Task 1. A mismatch is a fail-closed blocker, not permission to update the pinned identity.
- runStage2 stays byte-identical to the authority, including signature, candidate order, fits{position} = fitAllOrders(...), checkpoint cadence/variables, error handling, and Resume=false behavior.
- fitAllOrders(row, scanRow, rawFile, dopplerSign, cfg) keeps its Frozen signature. The qualified GPU device is initialized once per task, after all preflights and before Stage0; never per window/order/path. Device loss fails closed; no CPU fallback.
- Gather and validate the whole fit inside candidate fitAllOrders before it returns. No nested gpuArray may enter runStage2, the whole-fits checkpoint, stage2Fits, flattening, Stage3, or Stage4.
- Preserve Stage2 search order, grids, thresholds, BIC, refinement, stopping, and path semantics. Stage3/Stage4 remain Frozen consumers of in-memory fits; Stage4 may seed from all L1–L4 models.
- The only destinations are scenes/F1023_V70_D0117_P2/sage_results/gpu_candidate_fulltask_20261005/G28_ch1 and scenes/F1023_V120_D0121_P2/sage_results/gpu_candidate_fulltask_20261005/G03_ch2. Every task uses Resume=false; an existing destination blocks execution. Never overwrite, reuse, or resume.
- Candidate-only provenance is an independent candidate_provenance.json; do not add provenance fields to Frozen cfg.
- Comparisons use strict structural/classification gates and raw numeric deltas. Do not add scientific numeric tolerances. Stage4 confirmation uses only joint_valid == 1, joint_multipath_count > 0, and a corresponding stage4_joint_paths.is_multipath == 1 row.
- Task A is one invocation. Even if it passes locally, publish code, source-diff audit, validator, and lightweight evidence, then stop for GPT review. Task B requires new explicit GPT/user authorization after that review and is a separate invocation; Task A PASS never dispatches Task B.
- Later MATLAB smoke, MATLAB tests, and full-task execution must use the validated non-admin TJ-CHANNEL account Jing_ in PowerShell 7, not a Codex-launched MATLAB process. Resolve MATLAB with Get-Command -Name 'matlab' -CommandType Application; use ProcessStartInfo.ArgumentList with separate -batch and expression arguments and single-quoted MATLAB char literals. Do not hardcode a MATLAB installation path.
- The current phase creates only this plan. No candidate output namespace, raw-IQ read, MATLAB/GPU run, Engineering/Paper Handoff edit, batch resume, or business-branch commit/push.

## Review Focus

1. **Wrong Frozen source copied from the old review checkout.** Task 1 must hash the local bffc... authority before and after copy and reject the review-base 9a263f... source.
2. **Nested gpuArray reaches checkpoint/downstream.** Task 2 tests recursive fit validation and verifies it runs before fitAllOrders returns.
3. **Per-window GPU initialization returns.** Task 3 statically verifies exactly one task-entry gpuDevice initialization and none in fit/model/path functions.
4. **Candidate provenance contaminates cfg.** Task 3 and Task 4 verify provenance is written separately and absent from semantic cfg.
5. **Task A PASS starts Task B before GPT review.** Task 5's driver test proves a single-task invocation stops after Task A; Task 6 is gated on a new authorization and separate call.

---

## File Structure

### Candidate files created during a later implementation phase

- experiments/sage_gpu/full_task_candidate/run_nav_sage_pipeline_gpu_candidate.m — copied Frozen pipeline, candidate entry/output routing, and reviewed Stage2 dispatch.
- experiments/sage_gpu/full_task_candidate/assertCpuResidentFrozenFit.m — one responsibility: validate the Frozen fit schema/types and recursively fail if any nested value is a gpuArray.

### Validation files created during a later implementation phase

- experiments/sage_gpu/full_task_validation/Invoke-FullTaskGpuCandidateValidation.ps1 — single-task preflight/launch/compare coordinator; never schedules a second task.
- experiments/sage_gpu/full_task_validation/Compare-FullTaskGpuCandidateOutputs.m — independent formal-output comparison; it does not call candidate scientific functions.
- experiments/sage_gpu/full_task_validation/tests/Invoke-FullTaskGpuCandidateValidation.Tests.ps1 — source-boundary, launch arguments, lifecycle, namespace, provenance, and one-task-only Pester tests.
- experiments/sage_gpu/full_task_validation/tests/TestFullTaskGpuCandidateFitContract.m — fit schema and recursive CPU-residency tests using a small synthetic fit.
- experiments/sage_gpu/full_task_validation/tests/TestFullTaskGpuCandidateComparison.m — comparison-validator tests using temporary synthetic CSV/MAT fixtures.
- experiments/sage_gpu/full_task_validation/FULL_TASK_GPU_SOURCE_DIFF_AUDIT.csv — one row per source/function diff, allowed category, and pass/fail disposition.
- experiments/sage_gpu/full_task_validation/FULL_TASK_GPU_VALIDATION_RESULTS.csv — one row per full task with per-stage gates and task-level maxima.
- experiments/sage_gpu/full_task_validation/FULL_TASK_GPU_STAGE2_WINDOW_COMPARISON.csv — one row per evaluated window with structure, model-order margins, and raw numeric deltas.
- experiments/sage_gpu/full_task_validation/FULL_TASK_GPU_VALIDATION_SUMMARY.md — concise provenance, source-diff, Stage0–Stage4, performance, and gate summary.

### Generated only inside each candidate output namespace

- candidate_provenance.json and the candidate's Stage0–Stage4 outputs. These are local experimental outputs, not review-branch files; never publish raw IQ, MAT/HDF5, archives, or full result trees.

### Read-only inputs

- Authoritative Frozen source and the two formal CPU reference output namespaces in the approved spec.
- Qualified GPU source at the approved review branch: experiments/sage_gpu/stage2_window_173_gpu_probe.m and experiments/sage_gpu/selectSeparatedResidualCandidate.m.
- The published source audit and source excerpts; they remain unchanged.

No other helper is left as “as needed.” If these fixed files prove insufficient, stop and request design review rather than adding an unplanned subsystem.

## Verified source and launch identities

At plan creation, the authoritative local Frozen source is bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c. The review branch commit 672b86b0781fabb99803bc263a07018311f86862 contains the qualified GPU source files with these current SHA-256 identities:

| Source | Current SHA-256 | Use |
|---|---|---|
| experiments/sage_gpu/stage2_window_173_gpu_probe.m | BFE56AD02C99240257FDDD212BA43EE5606A81740B3DDA716C5947C433CBFA88 | Reuse/adapt its already-qualified GPU function bodies; exclude its window-probe entry and scratch/comparison harness. |
| experiments/sage_gpu/selectSeparatedResidualCandidate.m | A40C6459E66A384E85053589B270C5D2E112363872153FBF46DA5C56FD4BB1F5 | Reuse its qualified separated-candidate rejection/retry helper unchanged. |
| experiments/sage_gpu/stage2_window_173_probe.m | 90689A52A98AEB0B88305F43540BC0FC93AABE7FE3A57A74C1D82C5E4942B3CF | CPU experimental/reference evidence only; not an alternative scientific authority. |

The current business checkout does not contain stage2_window_173_gpu_probe.m; the published review branch does. Before implementation, verify these files from the reviewed branch and recompute all hashes. Any mismatch stops at QUALIFIED_GPU_SOURCE_IDENTITY_MISMATCH; do not rewrite equivalent GPU code from scratch or silently bless a changed source.

Run this from the reviewed branch worktree before implementation:

```powershell
Get-FileHash -Algorithm SHA256 -LiteralPath ./experiments/sage_gpu/stage2_window_173_gpu_probe.m, ./experiments/sage_gpu/selectSeparatedResidualCandidate.m, ./experiments/sage_gpu/stage2_window_173_probe.m
```

The existing validated launcher in scripts/sage_pipeline/Invoke-FrozenSageRerunSingle.ps1 resolves matlab.exe through Get-Command, builds ProcessStartInfo, sets UseShellExecute = $false, and adds -batch and the complete MATLAB expression as separate ArgumentList entries. It captures stdout/stderr and exit code. Reuse that native-argument transport pattern, not the production pipeline expression or its science-specific runner. Preserve the established smoke markers MATLAB_STARTUP_OK and MATLAB_ARGUMENT_TRANSPORT_OK.

---

## Task 1: Candidate source construction and Frozen-diff guard

**Files:**
- Create: experiments/sage_gpu/full_task_candidate/run_nav_sage_pipeline_gpu_candidate.m
- Create: experiments/sage_gpu/full_task_validation/Invoke-FullTaskGpuCandidateValidation.ps1 (source-boundary/preflight functions only in this task)
- Create: experiments/sage_gpu/full_task_validation/tests/Invoke-FullTaskGpuCandidateValidation.Tests.ps1

**Interfaces:**
- Consumes: the exact local Frozen source, the source audit's function inventory/hashes, and the pinned qualified-source identities above.
- Produces: a candidate copied from the bffc... authority, plus a source-boundary preflight that classifies every candidate delta as one of GPU_STAGE2_COMPUTATIONAL_DIFFERENCE, NON_SCIENTIFIC_PLUMBING_DIFF, or PROVENANCE_INSTRUMENTATION; any other delta is UNEXPECTED_DIFF and blocks.

- [ ] **Step 1: Verify the authoritative and qualified source identities.**

Run:

```powershell
Get-FileHash -Algorithm SHA256 -LiteralPath 'E:/GNSS_Multipath_Project/scripts/sage_pipeline/run_nav_sage_pipeline.m'
```

Before candidate construction, recompute the two qualified GPU source hashes from the reviewed branch. Expected Frozen SHA is exactly bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c; the qualified source identities must match the table above. Stop on any mismatch.

- [ ] **Step 2: Copy the exact authority into the candidate path.**

The copy operation is the deliverable; do not invent a failing test for a byte-copy operation.

```powershell
if (Test-Path -LiteralPath ./experiments/sage_gpu/full_task_candidate/run_nav_sage_pipeline_gpu_candidate.m) { throw 'CANDIDATE_SOURCE_ALREADY_EXISTS' }
New-Item -ItemType Directory -Path ./experiments/sage_gpu/full_task_candidate
Copy-Item -LiteralPath ./scripts/sage_pipeline/run_nav_sage_pipeline.m -Destination ./experiments/sage_gpu/full_task_candidate/run_nav_sage_pipeline_gpu_candidate.m
```

Confirm the copied file initially has the same SHA-256 as the authoritative source before candidate edits. Change only the top-level candidate function name required to make the copied file callable as run_nav_sage_pipeline_gpu_candidate; do not change the production file.

- [ ] **Step 3: Write Pester tests for the source guard and run them before completing the guard.**

Add tests that assert: the authority path/hash is the local bffc... file; the old review 9a263f... copy is rejected; immutable function bodies match the authority; and an injected/unclassified diff returns UNEXPECTED_DIFF and blocks. The no-test-for-copy exception above applies only to the mechanical copy, not to the guard logic.

- [ ] **Step 4: Implement and run the minimal source-boundary guard.**

Compare candidate and authority by top-level function boundary and exact function text. Keep these authoritative bodies unchanged: runStage2, flattenStage2, evaluatePersistence, runJointStage, and every Stage0/Stage1 scientific function. Preserve the audit-recorded function hashes for runStage2 (96dc162a17cf87dde5300ccd902a8a08fa6c0c10643c0d7b446a214ff1eb8f8e), flattenStage2 (22c15b598ff84df379710b2ec9ce4d054855fb5a2fc4786c4b7d734da4b16d2c), evaluatePersistence (221746eb016bdc94aacd9d95a5a89b4315c266a9418fd897f9962b3934940152), and runJointStage (cc0ab1a13007aeceb805bde92f74b806de5136ed45a5e9f645544fc40707a52f) as normalized audit fingerprints, and additionally require exact text equality for those bodies in the candidate. runStage2 must be byte-identical.

For the remaining diffs, allow only candidate entry/output routing/provenance and the qualified Stage2 computation/data movement. Emit the planned source-diff CSV schema; do not suppress or auto-classify an unknown hunk.

Run:

```powershell
pwsh -NoProfile -Command "Invoke-Pester -Path ./experiments/sage_gpu/full_task_validation/tests/Invoke-FullTaskGpuCandidateValidation.Tests.ps1 -Output Detailed"
git diff --check
```

Expected: all source-guard tests pass; zero UNEXPECTED_DIFF; production Frozen SHA remains unchanged.

**Commit:** git add only the candidate and source-guard files, then commit as feat: scaffold frozen full-task GPU candidate.

## Task 2: Qualified GPU Stage2 integration and CPU-resident fit contract

**Files:**
- Modify: experiments/sage_gpu/full_task_candidate/run_nav_sage_pipeline_gpu_candidate.m
- Create: experiments/sage_gpu/full_task_candidate/assertCpuResidentFrozenFit.m
- Create: experiments/sage_gpu/full_task_validation/tests/TestFullTaskGpuCandidateFitContract.m

**Interfaces:**
- Consumes: Task 1 candidate/source guard; fitAllOrdersGpu and its helper bodies from the hash-pinned stage2_window_173_gpu_probe.m; the unchanged selectSeparatedResidualCandidate.m.
- Produces: the candidate fitAllOrders implementation with the Frozen signature and a validated, completely CPU-resident fit before return.

- [ ] **Step 1: Write MATLAB unit tests for the returned-fit contract.**

Test the exact required top-level fields windowId, catalogIndex, recordingTimeS, towS, models, selectedOrder, errorMessage; four L=1..4 model entries and their required fields; path fields delaySamples, dopplerHz, alpha, score; and the CPU types double, logical, and complex double. Include a nested gpuArray inside a model/path field and require the recursive contract checker to fail closed. Test a complete CPU-only synthetic fit as the passing fixture.

- [ ] **Step 2: Add the recursive contract checker with one responsibility.**

Implement assertCpuResidentFrozenFit(fit) in its fixed path. It validates the required Frozen fit/model/path schema and recursively checks cells and struct fields for any gpuArray; it throws NO_GPUARRAY_IN_RETURNED_FIT on leakage. It does not estimate paths or alter values.

- [ ] **Step 3: Replace only the candidate fitAllOrders computational body with the qualified GPU path.**

Keep the exact signature:

```matlab
fitAllOrders(row, scanRow, rawFile, dopplerSign, cfg)
```

Preserve Frozen preparation order:

```text
loadNavWipedFortyMs
→ makeSignalContext
→ qualified fitAllOrdersGpu
→ gather complete fit
→ assertCpuResidentFrozenFit
→ return
```

Copy/adapt the already-qualified GPU function bodies; do not reimplement them, alter grids/precision/order/BIC/separation retry, or import the probe's task-level gpuDevice initialization. Keep selectSeparatedResidualCandidate.m unchanged.

- [ ] **Step 4: Verify checkpoint safety without running a full task.**

Use the synthetic-fit MATLAB tests and source-boundary test to prove the recursive CPU-residency check occurs before the candidate fitAllOrders return and before unchanged runStage2 performs fits{position} = fitAllOrders(...) and saves the whole fits collection. Do not use a full-task run as the only checkpoint-safety test.

Run:

```powershell
pwsh -NoProfile -Command "Invoke-Pester -Path ./experiments/sage_gpu/full_task_validation/tests/Invoke-FullTaskGpuCandidateValidation.Tests.ps1 -Output Detailed"
```

Run the MATLAB unit tests through the validated PowerShell/.NET argument-list launcher as described under Task 3; require NO_GPUARRAY_IN_RETURNED_FIT=YES for the CPU fixture and expected rejection for the nested-GPU fixture.

**Commit:** commit only the candidate Stage2 and fit-contract test changes as feat: integrate qualified GPU Stage2 fit contract.

## Task 3: Candidate entry, namespace, provenance, and GPU lifecycle

**Files:**
- Modify: experiments/sage_gpu/full_task_candidate/run_nav_sage_pipeline_gpu_candidate.m
- Modify: experiments/sage_gpu/full_task_validation/Invoke-FullTaskGpuCandidateValidation.ps1
- Modify: experiments/sage_gpu/full_task_validation/tests/Invoke-FullTaskGpuCandidateValidation.Tests.ps1

**Interfaces:**
- Consumes: Task 1 source-boundary guard and Task 2 CPU-resident fitAllOrders.
- Produces: one-task CLI:
  - Action RunUnitTests
  - Action Preflight -Task TaskA|TaskB
  - Action RunAndCompare -Task TaskA|TaskB

  The driver handles exactly one named task per invocation and never dispatches the next task.

- [ ] **Step 1: Write Pester tests for lifecycle, identity, routing, and fail-closed behavior.**

Cover the five Review Focus cases. Specifically assert a single gpuDevice(...) initialization in the candidate entry after every preflight and before Stage0; no initialization/reset in fitAllOrders, per-window, per-order, or per-path code; no CPU fallback; exact task-to-namespace mapping; Resume=false; output-collision rejection; four-way task identity consistency (candidate request, formal reference context, candidate cfg/input identity, and helper requested identity); candidate provenance fields absent from cfg; and no Task B dispatch after Task A PASS.

Use small pure-function/process-start fixtures; do not build a general mocking framework or launch a full task in Pester.

- [ ] **Step 2: Implement candidate entry and fixed output routing.**

Expose function result = run_nav_sage_pipeline_gpu_candidate(sceneId, prn, varargin) with the existing Frozen name/value input contract. Accept only the two allowlisted task identities and their explicit channels. Fail closed unless Resume=false.

Run the preflights in this order: Frozen SHA; task/input identity; reference-output identity; GPU availability; exact candidate destination nonexistence. Only after all pass, initialize the selected device exactly once with gpuDevice(...), before Stage0. Record the selected device name. Do not reset/reinitialize later and do not silently fall back to CPU.

Use only these task destinations:

```text
TaskA: scenes/F1023_V70_D0117_P2/sage_results/gpu_candidate_fulltask_20261005/G28_ch1
TaskB: scenes/F1023_V120_D0121_P2/sage_results/gpu_candidate_fulltask_20261005/G03_ch2
```

The output route is plumbing only; keep raw/tracking/telemetry/navigation inputs and scientific cfg identical to the formal task.

- [ ] **Step 3: Write candidate provenance separately from Frozen cfg.**

Write candidate_provenance.json inside the selected candidate output namespace with frozen_source_sha256, gpu_candidate_source_sha256, qualified_gpu_stage2_source_identity, execution_timestamp, scene_id, prn, tracking_channel, resume=false, reference_output_namespace, candidate_output_namespace, and gpu_identity. Do not add any of these candidate-only fields to cfg.

- [ ] **Step 4: Implement the single-task PowerShell 7 driver.**

Resolve MATLAB using Get-Command -Name 'matlab' -CommandType Application. Build System.Diagnostics.ProcessStartInfo with UseShellExecute=$false, redirected stdout/stderr, and separate ArgumentList entries for -batch and the full MATLAB expression. Preserve single-quoted char literals and capture process exit code/stdout/stderr.

RunUnitTests runs the MATLAB test folder only. Preflight verifies source/input/reference/GPU/destination gates but does not create the namespace or read raw-IQ content. RunAndCompare performs exactly one named candidate task and invokes the independent comparison; it exits after recording that task's terminal result. It must not loop over, infer, or enqueue another task.

Before a candidate task is eligible, run the existing startup and argument-transport smoke expressions; require exit code 0 and markers MATLAB_STARTUP_OK and MATLAB_ARGUMENT_TRANSPORT_OK.

For `Action RunUnitTests`, send this complete expression as the single value following `-batch` in `ProcessStartInfo.ArgumentList`:

```matlab
results = runtests('experiments/sage_gpu/full_task_validation/tests'); assert(~isempty(results) && all([results.Passed]), 'FULL_TASK_GPU_TESTS_FAILED')
```

The startup smoke remains `disp('MATLAB_STARTUP_OK')`. The argument-transport smoke must reuse the currently validated expression/marker check from `Invoke-FrozenSageRerunSingle.ps1`; do not invent a new shell-quoting path. In both cases, `-batch` and the expression are separate `ArgumentList` entries.

- [ ] **Step 5: Run driver boundary tests and review the emitted source diff.**

Run:

```powershell
pwsh -NoProfile -Command "Invoke-Pester -Path ./experiments/sage_gpu/full_task_validation/tests/Invoke-FullTaskGpuCandidateValidation.Tests.ps1 -Output Detailed"
pwsh -NoProfile -File ./experiments/sage_gpu/full_task_validation/Invoke-FullTaskGpuCandidateValidation.ps1 -Action Preflight -Task TaskA
git diff --check
```

Expected: lifecycle and destination gates pass without creating a candidate namespace; any source, identity, GPU, or collision mismatch blocks.

**Commit:** commit only entry/driver/provenance tests as feat: add guarded single-task GPU candidate entry.

## Task 4: Independent full-task comparison validator

**Files:**
- Create: experiments/sage_gpu/full_task_validation/Compare-FullTaskGpuCandidateOutputs.m
- Modify: experiments/sage_gpu/full_task_validation/Invoke-FullTaskGpuCandidateValidation.ps1
- Create: experiments/sage_gpu/full_task_validation/tests/TestFullTaskGpuCandidateComparison.m
- Modify: experiments/sage_gpu/full_task_validation/tests/Invoke-FullTaskGpuCandidateValidation.Tests.ps1

**Interfaces:**
- Consumes: formal reference output directory, candidate output directory, exact task identity, and candidate provenance.
- Produces: strict structural/classification verdicts, raw numeric differences, one task-level results row, one row per Stage2 evaluated window, and no writes to either scientific output tree.

- [ ] **Step 1: Write comparison tests using temporary synthetic fixtures.**

Test each comparison boundary and a mismatch fixture for every stage. Ensure the validator fails on a schema/order/identity/label/classification mismatch and still reports raw numeric deltas without a tolerance. Fixtures live in a temporary directory and are removed by test cleanup; formal/candidate result folders are not fixtures.

- [ ] **Step 2: Implement Stage0/Stage1 exact CSV and semantic MAT checks.**

For Stage0, apply the exact CSV rule to stage0_valid_symbols.csv and stage0_valid_40ms_windows.csv. Compare stage0_nav_catalog.mat semantically on symbolCatalog, windowCatalog, and Frozen scientific/configuration semantics in cfg.

For Stage1, apply the same exact CSV policy to stage1_nav_fast_scan.csv. Compare stage1_nav_fast_scan.mat on stage1Table, dopplerSignUsed, and Frozen cfg semantics; compare stage1_nav_progress.mat on records, completed, and Frozen cfg semantics. Never compare a whole MAT binary hash.

Ignore only approved candidate/run metadata differences (runContext.outputDir, candidate namespace/path, createdAtUtc, relocation receipt, candidate provenance record, overview path/image bytes). Still require the same scene, PRN, channel, raw/tracking/telemetry input identity, and sample rate after path-separator normalization. Candidate-only provenance must remain outside cfg.

- [ ] **Step 3: Implement Stage2 per-window and task-level comparisons.**

For each evaluated window compare identity, L1–L4 validity, selected L, selected path count/order, and DIRECT/MPC labels. At task level compare evaluated windows, model rows, selected rows, selected paths, direct count, and MPC count. Emit maximum absolute/relative deltas for delay, Doppler, relative power, complex alpha when formal evidence exists, path score, RSS, and BIC. Emit CPU/GPU best L, second-best L, and BIC margin per evaluated window plus minimum margin and task/window. Margins are diagnostic only.

- [ ] **Step 4: Implement Stage3 and Stage4 dependency-aware comparisons.**

Stage3 compares center window identity, selected L, MPC/path identity, excess delay, relative Doppler, relative power, match pattern, matched-window count, longest consecutive count, persistence_pass, and reliable-center identity/classification. Match according to Frozen semantics (excess delay relative to direct, relative Doppler, relative power), not a new UUID.

Stage4 compares center identity, joint-result/snapshot count, selected L, joint_valid, joint_multipath_count, snapshot wins, path count/order, DIRECT/MPC labels, and confirmation classification. Require explicit STAGE4_RESULT_IDENTITY_MATCH and STAGE4_CONFIRMATION_CLASSIFICATION_MATCH. Apply only the project's strict confirmed criterion; do not infer a confirmed event from Stage2/Stage3.

- [ ] **Step 5: Emit the fixed lightweight report artifacts and test the validator.**

Write:
- FULL_TASK_GPU_SOURCE_DIFF_AUDIT.csv: source/function, authority/candidate hashes, allowed diff category, status.
- FULL_TASK_GPU_VALIDATION_RESULTS.csv: one row per task, per-stage status/counts, maxima, margin summaries, and notes.
- FULL_TASK_GPU_STAGE2_WINDOW_COMPARISON.csv: one row per evaluated window, structural matches, per-order validity, deltas, and CPU/GPU model-order margins.
- FULL_TASK_GPU_VALIDATION_SUMMARY.md: provenance, source-diff disposition, stage verdicts, numeric differences, candidate wall time, GPU initialization, Stage2 GPU time, transfer-in/gather time, and gate outcomes. Compare full-task speedup only if a trustworthy same-scope CPU runtime exists; otherwise report FULL_TASK_SPEEDUP=NOT_COMPARABLE. Never extrapolate the 14-window Stage2 timings.

Run:

```powershell
pwsh -NoProfile -File ./experiments/sage_gpu/full_task_validation/Invoke-FullTaskGpuCandidateValidation.ps1 -Action RunUnitTests
pwsh -NoProfile -Command "Invoke-Pester -Path ./experiments/sage_gpu/full_task_validation/tests/Invoke-FullTaskGpuCandidateValidation.Tests.ps1 -Output Detailed"
git diff --check
```

Expected: all MATLAB and PowerShell tests pass; comparison fixtures prove strict structural failure and raw-delta reporting.

**Commit:** commit only validator and its tests as feat: add independent full-task GPU comparison validator.

## Task 5: Task A — G28/ch1 full-task candidate and mandatory GPT review gate

**Files:**
- Read: formal Task A reference output and its run context.
- Generate locally: scenes/F1023_V70_D0117_P2/sage_results/gpu_candidate_fulltask_20261005/G28_ch1/
- Generate/publish lightweight evidence: the four validation files listed in Task 4.

**Interfaces:**
- Consumes: candidate, source guard, launcher, and independent validator from Tasks 1–4; formal reference scenes/F1023_V70_D0117_P2/sage_results/rerun_20261003_frozen_v3/G28_ch1.
- Produces: one terminal Task A candidate result and a review bundle; no Task B invocation.

- [ ] **Step 1: Require separate authorization for Task A execution.**

Before this step, the implementation plan must be reviewed/approved and the user must explicitly authorize the Task A MATLAB/GPU run and its required raw-IQ access. This plan itself does not grant that execution authority.

- [ ] **Step 2: Run preflight and static validation for Task A only.**

From the normal non-admin TJ-CHANNEL account Jing_ PowerShell 7 session:

```powershell
pwsh -NoProfile -File ./experiments/sage_gpu/full_task_validation/Invoke-FullTaskGpuCandidateValidation.ps1 -Action Preflight -Task TaskA
```

Require exact Frozen/source/helper hashes, all identity/reference checks, canUseGPU, the validated GPU identity, and destination absence. The preflight must not create the output namespace or read raw-IQ content.

- [ ] **Step 3: Execute exactly Task A and compare it.**

Only after Step 1 authorization and Step 2 pass, run:

```powershell
pwsh -NoProfile -File ./experiments/sage_gpu/full_task_validation/Invoke-FullTaskGpuCandidateValidation.ps1 -Action RunAndCompare -Task TaskA
```

The driver's single MATLAB `-batch` expression is:

```matlab
run_nav_sage_pipeline_gpu_candidate('F1023_V70_D0117_P2',28,'TrackingChannel',1,'ProjectRoot','E:/GNSS_Multipath_Project','Resume',false)
```

Pass it as one `ArgumentList` entry after a separate `-batch` entry. The driver launches only F1023_V70_D0117_P2 / PRN 28 / channel 1, with Resume=false; it reads no other dataset, runs no batch, and does not enqueue Task B.

- [ ] **Step 4: Apply the full fail-closed gate.**

Require Stage0 exact CSV/semantic MAT; Stage1 exact CSV/semantic MAT; Stage2 structure; Stage3 structure/classification; Stage4 identity/classification; complete artifacts/schemas; and zero UNEXPECTED_DIFF. Record numeric differences exactly as observed. On any failure, stop, preserve outputs, mark Task B NOT_RUN, and publish the classified blocker for GPT review.

- [ ] **Step 5: Publish Task A code and lightweight evidence, then stop.**

Commit/push only the candidate source, fit-contract helper/tests, validation driver, independent validator/tests, source-diff CSV, task/window result CSVs, and summary Markdown to reports/gpu-qualification-stage-review-20261005. Exclude raw IQ, MAT/HDF5, archives, full candidate output directories, and unrelated worktree changes. After push, query the remote ref and verify REMOTE_HEAD equals the published commit.

Whether Task A passes or fails, stop here for GPT review of the actual candidate source, source-diff audit, validator, and Task A evidence. If Task A is a classified blocker, update Engineering Handoff as specified in Task 7 before publishing. A Task A PASS does not authorize Task B.

**Commit:** feat: validate full-task GPU candidate Task A (after a passing or classified terminal Task A outcome).

## Task 6: Task B — G03/ch2 only after new GPT authorization

**Files:**
- Read: formal Task B reference output and its run context.
- Generate locally: scenes/F1023_V120_D0121_P2/sage_results/gpu_candidate_fulltask_20261005/G03_ch2/
- Update only the lightweight validation CSV/summary files from Task 4.

**Interfaces:**
- Consumes: GPT-reviewed Task A code, source diff, validator, and results; explicit new GPT/user authorization; formal reference scenes/F1023_V120_D0121_P2/sage_results/rerun_20261003_frozen_v3/G03_ch2.
- Produces: one terminal Task B result and a second lightweight review bundle.

- [ ] **Step 1: Verify the new authorization gate.**

Do not start from local Task A PASS alone. Require a new explicit GPT/user authorization after review of the pushed Task A bundle. If absent, leave Task B NOT_RUN.

- [ ] **Step 2: Re-run hashes, preflight, and tests for Task B.**

```powershell
pwsh -NoProfile -File ./experiments/sage_gpu/full_task_validation/Invoke-FullTaskGpuCandidateValidation.ps1 -Action Preflight -Task TaskB
```

Require scene=F1023_V120_D0121_P2, PRN=3, channel=2, exact formal reference identity, output absence, current frozen/helper hashes, GPU availability, and Resume=false.

- [ ] **Step 3: Execute and compare only Task B.**

After Step 1 authorization and Step 2 pass:

```powershell
pwsh -NoProfile -File ./experiments/sage_gpu/full_task_validation/Invoke-FullTaskGpuCandidateValidation.ps1 -Action RunAndCompare -Task TaskB
```

The driver's single MATLAB `-batch` expression is:

```matlab
run_nav_sage_pipeline_gpu_candidate('F1023_V120_D0121_P2',3,'TrackingChannel',2,'ProjectRoot','E:/GNSS_Multipath_Project','Resume',false)
```

Pass it as one `ArgumentList` entry after a separate `-batch` entry. The process reads only Task B's required raw-IQ input and runs no other task. Apply the same strict Stage0–Stage4, artifact, source-diff, and numeric-reporting rules as Task A.

- [ ] **Step 4: Commit/push Task B evidence and stop for GPT review.**

Publish only the updated lightweight validation files and approved source/test changes; verify the remote branch head equals the new commit. Stop for GPT review. Do not start any pilot, batch, 20.46 MHz task, CIR, alpha export, ledger, or model fitting.

**Commit:** feat: validate full-task GPU candidate Task B (only after the separate authorization and terminal Task B outcome).

## Task 7: Conditional Engineering Handoff closure

**Files:**
- Modify only if this task's entry condition is met: docs/GNSS_SAGE_ENGINEERING_HANDOFF_CURRENT.md
- Never modify: docs/GNSS_SAGE_PAPER_HANDOFF_CURRENT.md

**Interfaces:**
- Consumes: a clearly classified terminal Task A blocker, or the terminal Task B validation result.
- Produces: a synchronized Engineering Handoff entry with hashes, review commit, pass/fail status, and execution provenance. No parallel status source.

- [ ] **Step 1: Check the update condition.**

Do not update the handoff for plan creation, implementation substeps, Task A PASS while awaiting GPT review, or a pending Task B authorization. Update only for a classified Task A blocker or after Task B reaches a terminal validation result.

- [ ] **Step 2: Record only evidenced engineering state.**

Record candidate/helper/test/validator hashes, Frozen SHA before/after, task-specific run and QA status, output namespace, actual raw-IQ/MATLAB/GPU scope, and review commit. Do not promote Planned/Implemented to Completed or claim production GPU enablement. Paper Handoff remains unchanged.

- [ ] **Step 3: Validate and publish the handoff only with its triggering review bundle.**

Run git diff --check; stage only the Engineering Handoff and allowed lightweight review artifacts; commit/push to the dedicated review branch and verify the remote head. Stop for GPT review.

## Plan Self-Review

- **Spec coverage:** candidate boundary, one-time GPU lifecycle, fit gather/CPU contract, Frozen downstream dependencies, output isolation, provenance, comparison rules, two task gates, evidence publication, and conditional handoff each map to Tasks 1–7.
- **Step scan:** tasks use checkable tests/commands; the only no-TDD exception is the exact source copy, verified by SHA and protected-function comparison.
- **Type consistency:** the Frozen fitAllOrders signature and fit/model/path field names match the approved spec; candidate provenance is separate from cfg.
- **Review Focus:** all five risks map to explicit source-guard, recursive-fit, lifecycle/provenance, and one-task-only checks before full-task execution.
- **Proportion:** seven dependent tasks use one candidate file, one contract helper, one single-task driver, one independent validator, and the minimum PowerShell/MATLAB tests and lightweight evidence files.
