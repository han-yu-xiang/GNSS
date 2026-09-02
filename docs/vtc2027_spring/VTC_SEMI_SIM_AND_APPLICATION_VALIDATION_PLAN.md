# VTC Three-Layer Algorithm and DLL-Bias Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status:** `DLL STUDY ABANDONED BY AUTHOR / NO FURTHER DLL EXECUTION / PARTIAL OUTPUT RETAINED / MATLAB UNTOUCHED`

**Goal:** Evaluate the frozen NAV-aided SAGE estimator through exactly three complementary validation layers. The DLL code-tracking-bias experiment has been abandoned by the author and is not eligible for paper admission.

**Architecture:** Layer 1 measures recovery error against known injected truth on G18 measured backgrounds with no Stage4-confirmed secondary path under the current criterion. Layer 2 repeats known-path injection on four G25/G05 windows that already contain Stage4-confirmed multipath, thereby testing incremental recovery in a real multipath mixture. Layer 3 uses the native G25/G05 Stage4 joint-fit containers to compare the frozen L=1 and selected multipath models without treating either estimate as physical ground truth.

**Tech Stack:** Python 3.12 + NumPy for NAV-aligned signal formation, isolated local/joint SAGE evaluation, MATLAB-v5 Stage4 read-only export, DLL correlation/discriminator calculations, contract tests, output audits, deterministic aggregation, and SHA-256 manifests. The approved validation must not start, attach to, pause, terminate, or otherwise interact with the concurrently running MATLAB production process. IEEEtran LaTeX remains gated until paper admission passes.

**Spec:** Author decision dated 2026-08-23; `docs/GNSS_SAGE_ENGINEERING_HANDOFF_CURRENT.md`; `docs/GNSS_SAGE_PAPER_HANDOFF_CURRENT.md`; `docs/vtc2027_spring/VTC_PLAN.md`; `docs/vtc2027_spring/EVIDENCE_MATRIX.md`.

## Fixed Scope

The author approved Python-only execution on 2026-08-23. The only authorized analyses are:

1. Layer 1: controlled injected-path recovery on G18 measured backgrounds;
2. Layer 2: additional known-path recovery on native G25/G05 confirmed-multipath backgrounds;
3. Layer 3: native G25/G05 L=1-versus-selected-model residual/BIC support;
4. a G25/G05 DLL code-tracking-bias case study — **abandoned by the author; do not execute or admit results**.

The following are explicitly outside this plan: new production tasks, full Stage0--Stage4 reruns, threshold tuning, new environment statistics, PVT or positioning-accuracy experiments, pseudorange-improvement claims, closed-loop receiver redesign, 20.46-MHz processing, and any modification of existing Figure/Table data.

## Global Constraints

- Commander/author approval has been granted for contract-listed raw-IQ access and the isolated Python local/joint validation estimator. MATLAB execution and manuscript scientific-scope unfreezing remain unauthorized.
- Existing `scenes/**/sage_results`, immutable requests, production manifests, QA reports, evidence CSVs, and Stage0--Stage4 thresholds are read-only.
- Approved execution may read only contract-listed raw-IQ intervals and must write only to `docs/vtc2027_spring/evidence/validation_v1/`; no production namespace may be reused, resumed, or overwritten.
- The estimator configuration is frozen from `scripts/sage_pipeline/run_nav_sage_pipeline.m`: maximum order 4, delay step 0.1 sample, minimum path separation 1.0 sample, Doppler step 5 Hz, minimum path power -25 dB, maximum coherence 0.98, sequential BIC gain 10, and five 20-ms joint snapshots.
- Injection truth parameters, trial order, random seed, matching rule, error tolerances, implementation hashes, and all source/configuration hashes must be frozen before the first approved Python validation run. No grid, seed, threshold, case, or tolerance may be changed after observing results.
- A G18 interval with `joint_valid=1` and `joint_multipath_count=0` means only “no Stage4-confirmed secondary path under the current criterion.” It is not a physical LOS, reflection-free, or multipath-free label.
- In Layer 2, only the added synthetic path has known ground truth. Native G25/G05 paths remain unknown physical components; agreement with their frozen Stage4 estimates is a consistency result, not accuracy against truth.
- Layer 3 is model-fit support on native observations, not independent physical validation.
- DLL claims are limited to discriminator zero-crossing/code-tracking bias in a stated receiver model. They are not PVT, pseudorange, or navigation-accuracy improvement claims.
- Every trial and every selected event must be retained in the audit outputs, including failed recovery and adverse DLL outcomes. No case-level cherry-picking is permitted.
- Results may enter the manuscript only after independent QA and a separate author/Commander paper-admission decision.

---

### Task 1: Freeze sources, cases, namespaces, and experiment contract

**Files:**

- Create: `scripts/analysis/vtc_validation/README.md`
- Create: `scripts/analysis/vtc_validation/freeze_validation_contract.py`
- Create: `scripts/analysis/vtc_validation/validation_contract.json`
- Create: `scripts/analysis/vtc_validation/test_validation_contract.py`
- Read only: `scripts/sage_pipeline/run_nav_sage_pipeline.m`
- Read only: `scenes/F1023_V70_D0120_P1/sage_results/nav_sage_v2/G18/`
- Read only: `scenes/F1023_V80_D0117_P8/sage_results/nav_sage_v2/G25/`
- Read only: `scenes/F1023_V70_D0120_P9/sage_results/nav_sage_v2/G05/`
- Read only: `scenes/F1023_V80_D0117_P8/gnss_sdr/config/F1023_V80_D0117_P8.conf`
- Read only: `scenes/F1023_V70_D0120_P9/gnss_sdr/config/F1023_V70_D0120_P9.conf`

**Interfaces:**

- Consumes: frozen Stage0 catalogs, Stage4 CSV/MAT artifacts, tracking/telemetry products, scene `run_context.json` files, GNSS-SDR configurations, and source raw-IQ paths recorded in run context.
- Produces: one immutable contract containing source paths/hashes, exact window IDs, injection grids, estimator/configuration hashes, output namespace, deterministic seed, matching rule, tolerances, and explicit execution permissions.

- [ ] Record the Layer-1 source as `F1023_V70_D0120_P1/G18/ch2`; select the first three chronological Stage4 rows satisfying `joint_valid=1` and `joint_multipath_count=0`, and store their exact center-window IDs.
- [ ] Record the four Layer-2/Layer-3/DLL confirmed event centers exactly: `F1023_V80_D0117_P8/G25/ch10` windows `985` and `970`, and `F1023_V70_D0120_P9/G05/ch10` windows `493` and `495`.
- [ ] Verify all four positive cases satisfy the fixed confirmed criterion: `joint_valid=1`, `joint_multipath_count>0`, and a matching `stage4_joint_paths.csv` row with `is_multipath=1`.
- [ ] Freeze Layer-1 grid: excess delay `{1.1, 3.0}` samples; relative Doppler `{-30, 0, +30}` Hz; relative power `{-5, -10, -15}` dB; center-snapshot relative phase `{0, pi/2, pi, 3pi/2}`; three backgrounds; five contiguous 20-ms snapshots. Total: `216` trials.
- [ ] Freeze Layer-2 grid: excess delay `{2.5, 4.0}` samples relative to the fitted direct component; relative Doppler `{-30, +30}` Hz; relative power `{-8, -12, -16}` dB; center-snapshot relative phase `{0, pi/2, pi, 3pi/2}`; four confirmed-multipath backgrounds; five contiguous 20-ms snapshots. Total: `192` trials.
- [ ] Verify every Layer-2 injected delay is at least 1.0 sample from both the frozen direct component and the frozen native confirmed secondary component; reject the contract before execution if this condition fails for any case.
- [ ] Freeze truth matching as one-to-one minimum-cost assignment over non-direct recovered paths, using normalized cost `abs(delay_error)/0.2 + abs(doppler_error)/5 + abs(power_error)/2`; an injected path is recovered only when all three absolute errors meet the tolerances below.
- [ ] Freeze recovery tolerances: delay error `<=0.2` sample, relative-Doppler error `<=5` Hz, and relative-power error `<=2` dB. Continuous errors and failure reasons must still be reported when a path misses tolerance.
- [ ] Freeze deterministic seed `20270823`; injection phase evolves across snapshots according to the injected relative Doppler rather than being independently randomized per snapshot.
- [ ] Verify both recorded GNSS-SDR configurations contain `Tracking_1C.early_late_space_chips=0.5` and `Tracking_1C.dll_bw_hz=4.0`; hash both configuration files.
- [ ] Verify the contract rejects any output under `scenes/**/sage_results`, any `Resume=true`, any 20.46-MHz source, any unlisted raw-IQ interval, and any mutation of current evidence CSVs.
- [ ] Run `python scripts/analysis/vtc_validation/test_validation_contract.py` (or `pytest -v` if pytest is installed); expected result: all contract, source-identity, grid-count, case-criterion, and namespace-isolation tests pass.

### Task 2: Layer 1 — controlled recovery on G18 measured backgrounds

**Files:**

- Create: `scripts/analysis/vtc_validation/run_layer1_controlled_recovery.py`
- Create: `scripts/analysis/vtc_validation/vtc_validation_common.py`
- Create: `scripts/analysis/vtc_validation/audit_layer1_outputs.py`
- Create: `scripts/analysis/vtc_validation/test_layer1_outputs.py`
- Create during approved execution: `docs/vtc2027_spring/evidence/validation_v1/layer1_controlled_trials.csv`
- Create during approved execution: `docs/vtc2027_spring/evidence/validation_v1/layer1_controlled_summary.csv`
- Create during approved execution: `docs/vtc2027_spring/evidence/validation_v1/layer1_controlled_manifest.json`

**Interfaces:**

- Consumes: Task 1 contract; the three G18 NAV-aligned measured backgrounds; frozen navigation-bit wipe-off, C/A-code, delay/Doppler, model-order, and five-snapshot joint-estimation semantics.
- Produces: one row per injected trial with truth, selected order, matched recovered path, errors, validity/model metrics, failure classification, and source provenance.

- [ ] Load only the contract-listed five-snapshot G18 intervals and reconstruct the NAV-aligned measured observations with the frozen pipeline semantics.
- [ ] Estimate the direct component for each background, then inject one secondary C/A-code replica using the contract-frozen delay, relative Doppler, relative power, and phase.
- [ ] Run only the isolated local/joint validation estimator; do not execute production Stage0--Stage4 and do not create or modify a scene result directory.
- [ ] Apply the frozen one-to-one truth-matching rule; record selected order, injected-path recovery, continuous delay/Doppler/power errors, RSS, BIC, snapshot wins, validity flags, and failure reason.
- [ ] Aggregate recovery rate and median/90th-percentile absolute errors by relative power, excess delay, and relative Doppler; retain the overall result and all strata.
- [ ] Audit exactly `216` unique trials, finite truth fields, fixed hashes/seed, deterministic aggregation, complete failed-trial retention, and output isolation.
- [ ] Run `python scripts/analysis/vtc_validation/test_layer1_outputs.py -v`; expected result: schema, count, provenance, matching, tolerance, failure-retention, and aggregation tests pass.
- [ ] Label every resulting claim “controlled injected-path recovery on measured backgrounds with no Stage4-confirmed secondary path under the current criterion.” Do not call the backgrounds LOS or multipath-free.

### Task 3: Layer 2 — incremental recovery on confirmed-multipath backgrounds

**Files:**

- Create: `scripts/analysis/vtc_validation/run_layer2_multipath_stress.py`
- Create: `scripts/analysis/vtc_validation/audit_layer2_outputs.py`
- Create: `scripts/analysis/vtc_validation/test_layer2_outputs.py`
- Create during approved execution: `docs/vtc2027_spring/evidence/validation_v1/layer2_multipath_stress_trials.csv`
- Create during approved execution: `docs/vtc2027_spring/evidence/validation_v1/layer2_multipath_stress_summary.csv`
- Create during approved execution: `docs/vtc2027_spring/evidence/validation_v1/layer2_multipath_stress_manifest.json`

**Interfaces:**

- Consumes: Task 1 contract; the four native G25/G05 confirmed-multipath five-snapshot observations; their frozen Stage4 direct/secondary estimates; the frozen Layer-2 injection grid and estimator configuration.
- Produces: one row per stress trial with known injected-path recovery metrics plus separate native-secondary consistency fields.

- [ ] Load only G25 windows `985/970` and G05 windows `493/495`, preserving the native measured direct and secondary components rather than cancelling or replacing them before injection.
- [ ] Inject one additional synthetic path at the contract-frozen parameters, producing a real measured multipath background plus one known added component.
- [ ] Run only the isolated local/joint validation estimator with maximum order 4; do not alter Stage0--Stage4 production outputs or confirmation thresholds.
- [ ] Match the known injected path by the Task 1 rule. Record its recovery and continuous errors independently of the selected model order; do not define success merely as `L>=3`.
- [ ] Match the native secondary component separately to the frozen Stage4 estimate and record retention and parameter drift as `native_path_consistency`; never label this drift as error against physical truth.
- [ ] Record path merging, order under-selection, order over-selection, injected-path miss, native-path displacement, invalid model, and numerical failure as distinct outcomes.
- [ ] Aggregate injected-path recovery and errors by native event, environment, injected power, delay, and Doppler; retain all `192` trials and all adverse outcomes.
- [ ] Audit exactly `192` unique trials, four source events, fixed hashes/seed, injected-path separation, deterministic matching, and strict output isolation.
- [ ] Run `python scripts/analysis/vtc_validation/test_layer2_outputs.py -v`; expected result: schema, count, source-case, truth-matching, native-consistency-label, failure-retention, and aggregation tests pass.
- [ ] Label this layer “incremental known-path recovery on measured backgrounds already containing Stage4-confirmed multipath.” Only the injected path has ground truth.

### Task 4: Layer 3 — native real-data L=1 versus selected-model support

**Files:**

- Create: `scripts/analysis/vtc_validation/export_layer3_native_model_support.py`
- Create: `scripts/analysis/vtc_validation/mat_v5_reader.py`
- Create: `scripts/analysis/vtc_validation/audit_layer3_outputs.py`
- Create: `scripts/analysis/vtc_validation/test_layer3_outputs.py`
- Create: `scripts/analysis/vtc_validation/audit_layer3_outputs.py`
- Create during approved execution: `docs/vtc2027_spring/evidence/validation_v1/layer3_native_model_support.csv`

**Interfaces:**

- Consumes: read-only `stage4_nav_joint_100ms.mat`, `stage4_joint_summary.csv`, and `stage4_joint_paths.csv` for G25 windows `985/970` and G05 windows `493/495`; specifically the stored `jointFits.models{1}` and frozen selected model for each event.
- Produces: four event-level rows and their five-snapshot L=1-versus-selected-model RSS/BIC comparison without rerunning SAGE.

- [ ] Export the stored five-snapshot `snapshotRss`, total RSS, BIC, validity, and path count for L=1 and the frozen selected model at each of the four confirmed event centers.
- [ ] Compute `rss_reduction_percent = 100*(RSS_L1-RSS_selected)/RSS_L1` and `delta_bic = BIC_L1-BIC_selected`; retain the five individual snapshot comparisons.
- [ ] Cross-check event IDs, selected order, total RSS/BIC, and path parameters against the Stage4 CSVs and independent QA reports.
- [ ] Verify no raw IQ is read and no local/joint estimator is called in this layer; it is an export and deterministic recomputation from the existing frozen Stage4 MAT containers.
- [ ] Report this only as native real-observation model-fit support. Do not describe it as reflector truth, parameter-accuracy validation, an independent dataset, or proof that every residual component is physical multipath.

### Task 5: DLL code-tracking-bias experiment

**Status:** **ABANDONED BY AUTHOR on 2026-08-25.** Do not resume or extend this task. Existing partial or smoke outputs are retained for provenance only and must not be treated as formal validation evidence or inserted into the manuscript.

**Files:**

- Create: `scripts/analysis/vtc_validation/run_dll_code_bias_study.py`
- Create: `scripts/analysis/vtc_validation/audit_dll_code_bias_outputs.py`
- Create: `scripts/analysis/vtc_validation/test_dll_code_bias_outputs.py`
- Create during approved execution: `docs/vtc2027_spring/evidence/validation_v1/dll_code_bias_cases.csv`
- Create during approved execution: `docs/vtc2027_spring/evidence/validation_v1/dll_code_bias_summary.csv`
- Create during approved execution: `docs/vtc2027_spring/evidence/validation_v1/dll_code_bias_manifest.json`

**Interfaces:**

- Consumes: the four G25/G05 confirmed-event path models, their contract-listed native five-snapshot observations, Layer-1 and Layer-2 recovery-error distributions, and the two recorded GNSS-SDR tracking configurations.
- Produces: per-snapshot and per-event discriminator zero-crossing code bias before cancellation, after fitted-model cancellation, and after error-aware cancellation, in chips and meters.

- [ ] Confirm the exact discriminator implemented by the locally evidenced GNSS-SDR build. If its formula cannot be established, use the normalized noncoherent early-minus-late envelope discriminator and label the study an illustrative receiver model.
- [ ] Use the recorded early/late spacing of `0.5` chip. Record the configured DLL bandwidth of `4.0` Hz as provenance, but do not use it to imply a dynamic closed-loop simulation; this experiment is a static/quasi-static discriminator zero-crossing study.
- [ ] For each of the four confirmed events, read only its contract-listed five native snapshots and solve the per-snapshot complex path amplitudes by least squares with the frozen Stage4 path delays and Dopplers; do not claim that these amplitude vectors were stored in the Stage4 MAT file.
- [ ] Construct the fitted direct-plus-secondary correlation function for all five snapshots from the frozen path geometry and the reconstructed least-squares complex amplitudes.
- [ ] Define pre-cancellation code bias as the composite discriminator zero crossing relative to the fitted direct-path delay; compute it on a fixed code-offset grid and retain the sign.
- [ ] Subtract the fitted secondary component and recompute the zero crossing as a model-consistent upper-bound case; label it `fitted_model_cancellation`, not measured receiver improvement.
- [ ] Build `error_aware_cancellation` by applying every successful Layer-2 injected-path delay/Doppler/power error tuple to the native secondary-component cancellation model. Use Layer-1 errors only as a separately labeled controlled-background sensitivity reference, never as a replacement for Layer-2 stress errors.
- [ ] Convert chip bias to meters with `c/1.023e6`; retain chips, meters, sign, absolute bias, and cancellation-mode label.
- [ ] Report median and 10th/90th percentiles across the error-aware ensemble for each native event; retain any case in which cancellation worsens absolute bias.
- [ ] Optionally align `code_error_chips` and `code_error_filt_chips` from the tracking MAT files as receiver-internal diagnostics only; never treat them as independent truth or as positioning-error measurements.
- [ ] Do not report PVT accuracy, pseudorange improvement, positioning improvement percentage, or universal mitigation performance.
- [ ] Run `python scripts/analysis/vtc_validation/test_dll_code_bias_outputs.py -v`; expected result: source/configuration provenance, discriminator definition, unit conversion, zero-crossing sign, error-aware ensemble completeness, and adverse-case retention tests pass.

### Task 6: Independent QA and manuscript-admission gate

**Files:**

- Create: `docs/vtc2027_spring/evidence/VTC_THREE_LAYER_DLL_VALIDATION_QA_REPORT.md`
- Create: `docs/vtc2027_spring/evidence/validation_v1/validation_manifest.json`
- Create: `scripts/analysis/vtc_validation/run_independent_qa.py`
- Modify only after author admission: `docs/vtc2027_spring/EVIDENCE_MATRIX.md`
- Modify only after author admission: `docs/GNSS_SAGE_ENGINEERING_HANDOFF_CURRENT.md`
- Modify only after author admission: `docs/GNSS_SAGE_PAPER_HANDOFF_CURRENT.md`

**Interfaces:**

- Consumes: Tasks 1--5 artifacts and all source/configuration hashes.
- Produces: independent verdicts for execution isolation, numerical correctness, scientific semantics, and paper usability.

- [ ] Verify raw-IQ reads were limited to contract-listed intervals and no production artifact, current evidence file, Figure, Table, or manuscript file changed during Tasks 1--5.
- [ ] Verify all source/output hashes, trial counts (`216` and `192`), units, signs, event mappings, matching assignments, and failed/adverse-case retention.
- [ ] Independently recompute one Layer-1 trial per power level, one Layer-2 trial per power level, all four Layer-3 event rows, and one DLL snapshot per native event.
- [ ] Issue separate verdicts: `LAYER1_CONTROLLED_QA`, `LAYER2_MULTIPATH_STRESS_QA`, `LAYER3_NATIVE_MODEL_QA`, `DLL_BIAS_QA`, and `PAPER_ADMISSION_RECOMMENDATION`.
- [ ] Define a paper-admission recommendation before viewing final aggregates: both injection layers must pass QA; Layer 1 must recover at least 80% of trials at each of `-5` and `-10` dB; Layer 2 must recover at least 70% of trials at each of `-8` and `-12` dB; and error-aware DLL cancellation must reduce median absolute bias in at least three of the four native events without excluding adverse cases.
- [ ] Treat Layer 3 as bounded supporting evidence rather than a success-rate gate; report all four native event comparisons regardless of sign or magnitude.
- [ ] If any QA verdict fails, retain artifacts and failure reasons; do not tune, delete, selectively rerun, or weaken the predeclared gate.
- [ ] Stop and request author/Commander review. This QA report may recommend manuscript admission but cannot authorize it.

### Task 7: Compact bilingual manuscript integration only after explicit admission

**Files:**

- Modify only after explicit author admission: `docs/vtc2027_spring/manuscript/latex/main.tex`
- Modify only after explicit author admission: `docs/vtc2027_spring/manuscript/VTC2027_Spring_draft.md`
- Modify only after explicit author admission: `docs/vtc2027_spring/manuscript/latex_cn_review/main_cn_review.tex`
- Modify only after explicit author admission: `docs/vtc2027_spring/manuscript/VTC2027_Spring_CN_REVIEW.md`
- Modify only after explicit author admission: `docs/vtc2027_spring/figures/scripts/generate_vtc_figures.py`

**Interfaces:**

- Consumes: QA-passed, explicitly admitted summaries only.
- Produces: synchronized English/Chinese text and at most one compact validation figure or table while preserving the five-page target.

- [ ] Add one compact Results subsection centered on controlled recovery, multipath-background stress, native model support, and DLL code-bias implication.
- [ ] Prefer one two-panel figure: Layer-1/Layer-2 recovery and error in panel (a), and DLL zero-crossing bias before/error-aware-after cancellation in panel (b).
- [ ] Keep Layer-3 residual/BIC support to one sentence or one compact table row group for the four native events.
- [ ] State explicitly that only injected paths have known truth, G25/G05 native paths are SAGE-confirmed estimates, and the DLL result is a signal-level receiver-model case study.
- [ ] Do not add a generic “limited sample” concession to the abstract or conclusion; use positive but evidence-bounded wording and disclose the precise validation boundary where the result is presented.
- [ ] Do not change existing environment counts, confirmed event/path counts, Figure 1--4 data, Table I--II data, or Stage0--Stage4 scientific semantics.
- [ ] Compile English and Chinese LaTeX, verify five pages or fewer, inspect every page, and reject undefined citations/references, overfull boxes, clipped graphics, inconsistent bilingual numbers, or altered frozen scientific counts.

## Decision Point

Current decision: `AUTHOR_APPROVED_PYTHON_EXECUTION_2026-08-23`.

Execute the approved Python-only validation in this order:

```text
Task 1 contract freeze
  -> Task 2 Layer 1 controlled recovery
  -> Task 3 Layer 2 multipath-background stress
  -> Task 4 Layer 3 native model support
  -> Task 5 DLL code-bias study
  -> Task 6 independent QA and paper-admission recommendation
  -> STOP for author decision
  -> Task 7 only if explicitly admitted
```

Contract-listed raw-IQ reads and the isolated Python validation estimator are authorized. MATLAB execution, production-runner interaction, Stage0--Stage4 reruns, manuscript edits, and handoff updates remain prohibited until their separate gates are satisfied.
