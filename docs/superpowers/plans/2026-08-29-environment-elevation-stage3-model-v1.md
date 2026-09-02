# Environment × Elevation Stage3 Academic Path Model V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first frozen-contract Environment × Elevation statistical model from the 783-row academic Stage3 population using weighted observations, grouped validation, hierarchical marginals, supported joint dependence, scene/run bootstrap uncertainty, and an independent read-only QA audit.

**Architecture:** The builder reads only the QA-approved Stage3 statistical-unit namespace, the frozen provenance files, and the existing Stage4 confirmed-path partition for sensitivity comparison. It uses the already audited reciprocal algorithm-track IDs and fixed observation weights; it never recomputes track membership, opens raw IQ, invokes MATLAB/SAGE, or modifies existing scientific namespaces. A separate auditor rereads the builder outputs and source hashes without importing builder implementation logic for the substantive checks.

**Tech Stack:** Python 3.12.9 from `D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe`, NumPy 2.5.1, SciPy 1.18.0, CSV/JSON, and the read-only distribution primitives in `scripts/analysis/channel_modeling/path_distribution_core.py`.

**Spec:** Current Commander attachment: “Build Environment × Elevation Stage3 Academic Path Model V1”.

## Global Constraints

- Use the frozen academic Stage3 population: 783 observations, 445 centers, 50 runs, 12 scenes, 18 PRNs, 716 elevation-ready observations, 366 algorithm-level tracks, and 72 Stage4 validation tracks.
- Primary unit is `WEIGHTED_OBSERVATION` with `weight_i = 1 / conservative_algorithm_track_size_i`; retain all 783 rows.
- Use scene/run clustered inference and deterministic scene-block bootstrap; do not use row-wise independence as the primary uncertainty model.
- Keep `Urban`, `Special Reflective`, `Mountain/Valley`, and `Highway/Open`; keep `LOW=[0,30)`, `MID=[30,60)`, `HIGH=[60,90]` and continuous `elevation_deg`.
- Preserve `Highway/Open–LOW` as `NO_DIRECT_SUPPORT`; never synthesize empirical observations for it.
- Evaluate delay with Lognormal/Gamma/Weibull and signed Doppler/power with Normal/Laplace/Student-t; select using grouped held-out likelihood, not in-sample likelihood alone.
- Compare global, environment, and environment×elevation levels; label support using scene count, run count, effective count, and grouped-validation evidence rather than raw rows alone.
- Estimate joint dependence only at supportable levels; explicitly distinguish global/environment copulas from cell-level parent-only dependence.
- Do not copy Stage4 family selections or copula parameters as priors; Stage4 is a separated high-confidence sensitivity baseline.
- Do not derive a Ricean K-factor unless physically identifiable; keep physical reflector lifetime out of scope.
- Do not start 20.46 MHz processing, new acquisition, MATLAB, SAGE, batch execution, raw-IQ reads, or automatic follow-up work.
- Write only the new namespace `dataset_generation_logs/channel_modeling/environment_elevation_stage3_path_model_v1_20260829_r1/` and the new report `docs/ENVIRONMENT_ELEVATION_STAGE3_ACADEMIC_MODEL_V1_REPORT.md`; preserve all existing outputs.

---

### Task 1: Freeze the Stage3 model input contract and pure statistical helpers

**Files:**
- Create: `scripts/analysis/channel_modeling/build_environment_elevation_stage3_path_model.py`
- Test: `scripts/analysis/channel_modeling/tests/test_environment_elevation_stage3_path_model.py`

**Interfaces:**
- Consumes: `stage3_path_population.csv`, `observation_to_track_nodes.csv`, `track_population.csv`, `policy_support_matrix.csv`, and `audit_manifest.json` from `stage3_statistical_unit_track_reassessment_20260829_r1`.
- Produces: `load_stage3_population(root) -> Stage3Input`, `weighted_rank(values, weights) -> ndarray`, `support_label(...) -> str`, `fit_grouped_families(...) -> FamilySelectionResult`, and deterministic weighted summary helpers used by later tasks.

- [ ] **Step 1: Write the failing test.**

  Add tests that require: fixed elevation bins; one-over-track-size weights; exact per-track weight conservation; weighted quantiles; support labels that distinguish zero direct support from sparse multi-scene support; and grouped family selection never using a row-random split.

- [ ] **Step 2: Run the tests to verify they fail.**

  Run:

  ```powershell
  & 'D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe' -m pytest scripts/analysis/channel_modeling/tests/test_environment_elevation_stage3_path_model.py -q
  ```

  Expected result: collection fails because the new builder module and its interfaces do not yet exist.

- [ ] **Step 3: Implement input loading and pure helpers.**

  Read the existing Stage3 node and track tables, assert 783 unique academic-eligible/persistence-pass observations, copy the frozen track IDs and weights without rebuilding the graph, retain all source provenance columns, and restrict formal cell fits to the 716 rows with valid continuous elevation. Implement weighted mean/quantile/Kish calculations, weighted empirical ranks, support labels, and candidate-family metadata using fixed candidate order.

- [ ] **Step 4: Run the tests to verify they pass.**

  Run the same command and also compile the new builder. Expected result: all pure-helper tests pass and no source artifact is written.

---

### Task 2: Implement grouped candidate fitting and hierarchical marginal outputs

**Files:**
- Modify: `scripts/analysis/channel_modeling/build_environment_elevation_stage3_path_model.py`
- Test: `scripts/analysis/channel_modeling/tests/test_environment_elevation_stage3_path_model.py`

**Interfaces:**
- Consumes: `Stage3Input` and pure weighted helpers from Task 1 plus `fit_family`, `cdf`, `ppf`, and `nearest_correlation` from `path_distribution_core.py`.
- Produces: `candidate_family_scores.csv`, `selected_marginal_models.csv`, `global_models.csv`, `environment_models.csv`, `environment_elevation_models.csv`, `weighted_parameter_summary.csv`, and `cell_support_matrix.csv`.

- [ ] **Step 1: Add failing tests for grouped scoring and hierarchical source rules.**

  Test that leave-one-scene-out scoring reports held-out scenes and weighted held-out likelihood; AIC/AICc/BIC are reported separately; a zero-support cell is `NO_DIRECT_SUPPORT` and references its environment parent; and a cell with direct evidence carries its continuous elevation and direct/effective support counts.

- [ ] **Step 2: Run the focused tests and observe the expected failures.**

  Run the focused test names with the fixed SciPy interpreter; expected result is failure because grouped scoring and model-row functions are not implemented.

- [ ] **Step 3: Implement the marginal fit layer.**

  Fit global and environment models on all 783 environment-ready Stage3 observations with frozen weights. Fit cell models only on elevation-ready rows. Use the global grouped-selected family for the formal hierarchical layer; fit local direct rows plus a fixed, documented parent pseudo-quantile prior only where direct data exist, and use the environment parent unchanged for `Highway/Open–LOW`. Record direct row count, sum of weights, Kish effective count, track/run/scene/PRN counts, family, parameter JSON, parent source, and support label for every model.

  For each candidate family and supported grouping, report weighted in-sample log likelihood, leave-one-scene-out held-out weighted log likelihood and normalized score, AIC/AICc/BIC where effective count makes them meaningful, fold scene IDs, and the formal selected-family flag. No candidate selection may use Stage4 rows.

- [ ] **Step 4: Run focused tests and a small in-memory fixture.**

  Verify all candidate families are evaluated, the formal family is chosen by grouped score, positive delay models reject nonpositive data, and the 12-cell output always contains an explicit `Highway/Open–LOW` no-support row.

---

### Task 3: Add joint dependence, uncertainty, and exploratory continuous-elevation diagnostics

**Files:**
- Modify: `scripts/analysis/channel_modeling/build_environment_elevation_stage3_path_model.py`
- Test: `scripts/analysis/channel_modeling/tests/test_environment_elevation_stage3_path_model.py`

**Interfaces:**
- Consumes: fitted marginal models and weighted Stage3 observations from Task 2.
- Produces: `joint_dependence_models.csv`, `scene_block_bootstrap.csv`, `run_block_sensitivity.csv`, and `continuous_elevation_diagnostics.csv`.

- [ ] **Step 1: Add failing tests for PSD copulas and grouped resampling.**

  Test weighted-rank copula matrices are symmetric with unit diagonal and positive-semidefinite after the fixed projection; scene bootstrap resamples complete scene blocks; run bootstrap resamples complete run blocks; and an empty cell never receives a direct cell copula.

- [ ] **Step 2: Implement supported joint dependence.**

  Build weighted rank-to-normal Gaussian-copula correlations globally and at environment level when scene/effective support is adequate. Estimate cell-specific dependence only when the pre-specified support gate is met; otherwise record `ENVIRONMENT_PARENT_ONLY` or `NO_DIRECT_SUPPORT` and point to the parent copula. Store correlation matrices, eigenvalue floor, direct/effective counts, scene/run counts, and copula source.

- [ ] **Step 3: Implement deterministic bootstrap summaries.**

  Use a frozen seed and 1000 scene-block replicates for global, environment, and directly supported cell scopes. Refit the frozen selected family in each replicate with the fixed observation weights and parent rule; record confidence intervals for weighted means, medians, 0.025/0.25/0.75/0.975 quantiles, and fit parameters. Run a parallel run-block sensitivity with the same number of replicates and a documented offset seed.

- [ ] **Step 4: Implement continuous-elevation exploration.**

  For each environment and parameter on elevation-ready rows, report weighted rank correlation, weighted linear slope/intercept, weighted R²/RMSE, elevation range, scene/run/effective counts, and scene-block slope intervals. Keep this diagnostic exploratory; do not replace LOW/MID/HIGH. The V2 decision must be `SUPPORTED`, `CONDITIONAL`, or `NOT_SUPPORTED` based on independent scene support and stability, not on a visually attractive trend.

- [ ] **Step 5: Run focused tests.**

  Confirm deterministic repeated bootstrap calls match exactly, all stored correlations are valid, and no row-wise bootstrap appears in the primary outputs.

---

### Task 4: Add Stage4 sensitivity and derived channel-statistics audits

**Files:**
- Modify: `scripts/analysis/channel_modeling/build_environment_elevation_stage3_path_model.py`
- Test: `scripts/analysis/channel_modeling/tests/test_environment_elevation_stage3_path_model.py`

**Interfaces:**
- Consumes: Stage3 model outputs and the existing QA-approved Stage4 path-parameter source for baseline comparison only.
- Produces: `observation_track_sensitivity.csv`, `stage3_stage4_sensitivity.csv`, `stage3_stage4_cdf_comparison.csv`, `derived_channel_statistics.csv`, and `persistence_duration_statistics.csv`.

- [ ] **Step 1: Add failing tests for separation and identifiability.**

  Test that Stage4 rows never change Stage3 family selection; Stage3 weighted/raw/track summaries remain separately labeled; Ricean K-factor is emitted as non-identifiable without a physical main/reference power definition; and track duration is labeled algorithm-observed persistence rather than physical lifetime.

- [ ] **Step 2: Implement observation-handling sensitivity.**

  Compare raw observation/clustered, weighted observation, and conservative track-median views for every supported cell using medians, IQR, selected quantiles, fitted family, and bootstrap intervals. Store the prior sensitivity values as comparison context without tuning the model to reduce them.

- [ ] **Step 3: Implement Stage4 high-confidence comparison.**

  Read only the existing Stage4 confirmed-path parameter partition. At global, environment, and supported cell scopes compare Stage3 weighted summaries against Stage4 strict-confirmed baseline summaries, CDF values on common grids, medians/IQR/quantiles, family-selection diagnostics, and separate bootstrap intervals. Preserve empty Stage4 cells and label low-support comparisons `INCONCLUSIVE` instead of forcing agreement.

- [ ] **Step 4: Implement bounded channel statistics.**

  Derive Stage3-observed center/track diagnostics: mean excess delay, power-weighted RMS delay spread when at least two Stage3 components exist, power-weighted Doppler centroid and RMS Doppler spread under the explicit relative-power diagnostic interpretation, algorithm-observed reliable-component count, aggregate and strongest relative multipath power, and algorithm-track persistence duration. Record identifiability and caveats for every statistic; do not compute Ricean K-factor.

- [ ] **Step 5: Run focused tests.**

  Verify Stage4 fields are comparison-only, derived statistics preserve scope/provenance, and no physical-truth wording is generated for track duration or component counts.

---

### Task 5: Write the new-only model namespace, manifest, receipt, and report

**Files:**
- Modify: `scripts/analysis/channel_modeling/build_environment_elevation_stage3_path_model.py`
- Create at runtime only: `dataset_generation_logs/channel_modeling/environment_elevation_stage3_path_model_v1_20260829_r1/`
- Create at runtime only: `docs/ENVIRONMENT_ELEVATION_STAGE3_ACADEMIC_MODEL_V1_REPORT.md`

**Interfaces:**
- Consumes: all completed builder results from Tasks 1–4.
- Produces: the requested model tables, `model_config.json`, `model_manifest.json`, `build_receipt.json`, `model_diagnostics.csv`, `sampling_contract.json`, and the final report. The namespace must be absent before creation and must never overwrite an existing directory.

- [ ] **Step 1: Add failing tests for new-only and manifest gates.**

  Test that an existing output directory or report causes a fail-closed refusal; the manifest records builder/core/source hashes and false raw-IQ/MATLAB/SAGE/batch/20.46 flags; and `Highway/Open–LOW` is retained as `NO_DIRECT_SUPPORT`.

- [ ] **Step 2: Implement one-shot build orchestration.**

  Preflight all input hashes, assert the Stage3 statistical-unit QA is `PASS`, create only the absent output directory, write all tables, verify model quantile/CDF normalization and finite draws, write the sampling contract, and write a build receipt with output hashes. Persist exact support counts, family-selection method, bootstrap seeds/replicates, copula support gates, and model limitations.

- [ ] **Step 3: Write the report.**

  Include the exact Commander decision block, cell support table, selected families and grouped-validation status, hierarchical/coplanar support decisions, bootstrap/run sensitivity, Stage3-vs-Stage4 conclusion, continuous-elevation V2 decision, derived-statistics identifiability, 20.46 MHz decision, acquisition decision, and execution/immutability records. The report must state that the result is a bounded Stage3 measurement-derived model, not all physical multipath truth.

- [ ] **Step 4: Run builder tests and one production build with the fixed SciPy interpreter.**

  Run all tests before the one-shot build. Execute the builder once into `environment_elevation_stage3_path_model_v1_20260829_r1`; do not rerun SAGE or create any execution request.

---

### Task 6: Implement and run an independent read-only QA auditor

**Files:**
- Create: `scripts/analysis/channel_modeling/audit_environment_elevation_stage3_path_model.py`
- Test: `scripts/analysis/channel_modeling/tests/test_audit_environment_elevation_stage3_path_model.py`
- Read only: `dataset_generation_logs/channel_modeling/environment_elevation_stage3_path_model_v1_20260829_r1/`

**Interfaces:**
- Consumes: builder output, model manifest/receipt, Stage3 statistical-unit manifest, frozen production hashes, and the original Stage3/Stage4 parameter inputs.
- Produces: `independent_qa_report.md`, `independent_qa_result.json`, and a final QA status without changing any builder or source file.

- [ ] **Step 1: Write failing auditor tests.**

  Test output completeness, 783-row preservation, exact per-track weight conservation, all 12 cells, empty Highway/Open–LOW preservation, finite/normalized distributions, PSD copulas, bootstrap grouping/seeds, Stage4 separation, hash immutability, and fail-closed manifest/receipt mismatches.

- [ ] **Step 2: Run auditor tests and observe expected failures.**

  Run the fixed-interpreter test command; expected result is failure because the independent auditor module is absent.

- [ ] **Step 3: Implement independent checks.**

  Re-read CSV/JSON outputs independently, recompute source counts and weights, recompute cell support and Kish values, validate stored family rows and quantile normalization, inspect bootstrap grouping metadata, compare all protected source hashes before/after, and assert no output is under `scenes`/`sage_results`. Do not import the builder’s fit or selection routines for the substantive checks.

- [ ] **Step 4: Run the independent QA.**

  Execute the auditor against the new namespace with the fixed SciPy interpreter. Expected result: `MODEL_QA=PASS_WITH_LIMITATIONS` or `MODEL_QA=PASS` only if every required gate passes; otherwise stop and report the exact failed gate without modifying source artifacts.

- [ ] **Step 5: Perform final verification.**

  Run Python compilation and all model/auditor tests, verify output and report hashes against the manifest, inspect `git status --short` for only the intended new code/tests/plan/report changes, and confirm no MATLAB/SAGE/batch process was started.

---

## Completion condition

The task is complete only when the model namespace, report, build receipt, manifest, independent QA artifacts, and exact Commander decision block exist; all model/auditor tests and hash gates pass; the existing Stage3/Stage4/model namespaces remain unchanged; and execution stops without starting 20.46 MHz or new data collection.
