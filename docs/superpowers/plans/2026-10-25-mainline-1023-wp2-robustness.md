# Mainline Stage2 WP2 robustness closure implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans inline; complete each task with targeted tests and a fresh whole-change review.

**Goal:** Add the missing robustness evidence needed to close WP2 without rerunning the V0 baseline or treating MPC/window rows as independent scenes.

**Architecture:** Reuse the pinned V0 MPC/window extracts, the V0 scene-LOSO fit-parameter table, and existing distribution helpers. Add a focused Python diagnostics module and runner that write only aggregate, coordinate-free outputs to a new versioned report directory. The runner never invokes production or opens signal/CIR payloads.

**Tech Stack:** Python 3.12, NumPy, pandas, SciPy, unittest.

**Spec:** `docs/ACADEMIC_CHANNEL_MODELING_MASTER_PLAN.md` (WP2 and acceptance boundaries), `docs/superpowers/plans/2026-10-24-mainline-1023-stage2-v0.md`, and the user's approved 2026-10-25 WP2 scope in this conversation.

## Global Constraints

- Preserve all 8,914 Stage2 MPC, 7,847 selected Stage2 windows, 83 runs and 13 scenes; these are conditional on Stage2 selection, not an unconditional Stage0 population.
- Use whole `scene_id` as the outer validation and uncertainty unit; same-scene PRNs and overlapping windows remain repeated observations.
- Reuse prior V0 fit/fold outputs where sufficient; do not rerun the V0 pipeline or tune criteria after seeing results.
- Tail diagnostics use train-fold fitted parameters and report sparse-tail support; do not turn low support into a pass or fail claim.
- Power-delay comparison is a predeclared scene-held-out predictive comparison of the V0 unconditional relative-power baseline and a linear conditional Gaussian candidate; no causal or universal-law claim.
- Count models are explicitly conditional on Stage2-selected windows and the observed Stage2 count support 0–3 (direct path plus at most three additional paths); never add unselected Stage0 windows as zero.
- Do not read raw IQ, MAT/HDF5/CIR payloads, invoke MATLAB/SAGE/GNSS-SDR, or touch Task 5 production/release/queue/monitoring. The real alpha export pilot remains deferred.
- Preserve existing untracked work. Add only exact WP2 files to commits; never overwrite V0 output directories.
- Create a new output directory with exclusive-create semantics and write aggregate tables/report/manifest only; no exact coordinates or private source-record identifiers.

## Review Focus

1. A fold's parameter ranking must use only candidate families for the same variable, scope and held-out scene; failed/support-invalid fits remain visible.
2. Tail calibration must use the fold's training parameters, not refit on the held-out scene, and must expose expected tail counts.
3. Predictive comparisons and uncertainty must aggregate by scene, not by MPC/window row; no random row split.
4. The count likelihood must be normalized on 0–3, use only Stage2-selected windows, and mark its estimand as selection-conditional and capped.
5. Input identities/counts/hashes must be checked before analysis; outputs must not contain precise position/height fields or change frozen V0 inputs.

---

### Task 1: Reuse V0 folds for parameter/rank stability and tail diagnostics

**Files:**
- Create: `scripts/channel_modeling/mainline_stage2_wp2.py`
- Test: `scripts/channel_modeling/tests/test_mainline_stage2_wp2.py`

**Interfaces:**
- Consumes: `analysis_mpc_rows.csv` and `scene_fold_scores.csv` from the pinned V0 run; `mainline_stage2_v0.DISTRIBUTIONS` and `VARIABLES`.
- Produces: `marginal_stability_rows(mpc, fold_scores, scopes)` and `tail_calibration_rows(mpc, fold_scores, quantiles)`; both return per-scene records plus equal-scene summaries.

- [x] Write tests for within-variable per-scene family ranks, fold parameter summaries, held-out tail coverage from saved fold parameters, and low expected-tail support flags.
- [x] Run `python -m unittest scripts.channel_modeling.tests.test_mainline_stage2_wp2.WP2Tests.test_marginal_rank_is_within_variable_and_scene -v` and verify the intended missing-interface failure.
- [x] Implement fold-table parsing/validation, parameter spread summaries, and p01/p05/p10/p90/p95/p99 held-out quantile calibration (positive-delay tails retain support rules).
- [x] Run the focused tests and then `python -m unittest scripts.channel_modeling.tests.test_mainline_stage2_wp2 -v`; expected all tests PASS, with failed/unsupported folds retained.

### Task 2: Test whether power-delay dependence improves new-scene prediction

**Files:**
- Modify: `scripts/channel_modeling/mainline_stage2_wp2.py`
- Test: `scripts/channel_modeling/tests/test_mainline_stage2_wp2.py`

**Interfaces:**
- Produces: `evaluate_power_delay_loso(mpc, bootstrap_iterations=2000, seed=20261025)` returning per-held-out-scene model scores/coefficients and an equal-scene paired summary.
- Baselines: the training-scene-weighted Normal marginal for `relative_power_db`; candidate: training-scene-weighted linear Gaussian `relative_power_db ~ excess_delay_chips`.

- [x] Add tests proving the held-out scene is excluded from parameter fitting, each training scene contributes equal total weight, and the summary resamples paired scene scores rather than rows.
- [x] Run the focused tests to observe RED before implementation.
- [x] Implement whole-scene LOSO, equal-scene training weights, paired held-out mean log-score/RMSE deltas and deterministic whole-scene bootstrap intervals; keep estimates descriptive with only 13 scenes.
- [x] Run all WP2 module tests; expected score rows cover each represented scene exactly once and no row-level p-values are emitted.

### Task 3: Evaluate only Stage2-selected-window MPC-count candidates

**Files:**
- Modify: `scripts/channel_modeling/mainline_stage2_wp2.py`
- Test: `scripts/channel_modeling/tests/test_mainline_stage2_wp2.py`

**Interfaces:**
- Produces: `evaluate_selected_count_loso(windows)` for empirical categorical, support-truncated Poisson and support-truncated NB2 candidates on integer support `{0,1,2,3}`.
- Input is exactly one row per unique `(run_id, window_id)` in `selected_window_rows.csv`; no Stage0-unselected rows are accepted.

- [x] Add tests for duplicate window identity rejection, count support enforcement, PMF normalization, zero-count preservation, scene-level holdout and no synthetic zero rows.
- [x] Run the focused tests and confirm the missing implementation fails for the intended reasons.
- [x] Implement scene-balanced training likelihood and equal-scene held-out log-score/RMSE summaries; keep unseen-category/support failures explicit.
- [x] Run all WP2 module tests; expected test folds are by complete scene, and outputs label the conditional/capped estimand.

### Task 4: Add pinned-input runner, real-data outputs, QA and handoff

**Files:**
- Create: `scripts/channel_modeling/run_mainline_stage2_wp2.py`
- Create: `reports/data_consolidation_20261003/mainline_1023_model_v1/wp2_<UTC>/` aggregate outputs and report
- Modify: `docs/ACADEMIC_CHANNEL_MODELING_MASTER_PLAN.md`
- Modify: `docs/GNSS_SAGE_ENGINEERING_HANDOFF_CURRENT.md`

**Interfaces:**
- Runner inputs: private C: V0 extracts `dataset_generation_logs/channel_modeling/mainline_1023_stage2_v0_20261024T132210Z/{analysis_mpc_rows.csv,selected_window_rows.csv}`; tracked V0 fold scores/manifest under `reports/.../v0_20261024T132210Z/`.
- Runner verifies `analysis_mpc_rows.csv` SHA256 `a2c26d0de655e0f6cf4a60cf2906bf4cfff7aa16bbc5f74bffb4e9b80dab306c`, `selected_window_rows.csv` SHA256 `fbc784ff169fca6d95907e39a56510d9be0b61ec3c1ef42e15235002be40061c`, and fold-table SHA256 `faad49468cb7d36ed070e54a8b9fdc564cdaa9bc3f682fed1eb391cfebbf03ca` as pinned in the V0 artifact manifest.
- Produces versioned aggregate CSVs, `wp2_report.md`, and `wp2_manifest.json` with input/code/output hashes and explicit limitations.

- [x] Add an end-to-end synthetic orchestration test covering input identity/count validation, output namespace exclusivity, required tables and no-coordinate output fields.
- [x] Run the end-to-end test RED, implement the minimal runner, then run the test GREEN and all WP2 tests.
- [x] Execute once against the pinned V0 extracts into a new unique output directory; do not repeat V0.
- [x] Independently recount table rows, scene-fold coverage, selected-window count histogram, fit ranks, tail-support flags, and paired prediction summaries from produced outputs; verify input hashes unchanged.
- [x] Perform read-only alpha candidate availability audit only (source/test inventory); do not load real MAT/HDF5 or invoke the exporter.
- [x] Update the Master Plan WP2 status/evidence and Engineering Handoff with the Task 5 timestamped stop sample and the later separately authorized recovery addendum, WP2 result paths, limitations and one next priority.
- [x] Run `python -m unittest scripts.channel_modeling.tests.test_mainline_stage2_wp2 scripts.channel_modeling.tests.test_run_mainline_stage2_wp2 -v`, `python -m py_compile scripts/channel_modeling/mainline_stage2_wp2.py scripts/channel_modeling/run_mainline_stage2_wp2.py`, and `git diff --check`; all passed.
- [ ] Commit only the new WP2 code, tests, aggregate report/tables, plan and the two authoritative documents; preserve every pre-existing untracked file. Push the existing review branch and update Draft PR #2 only after independent review; do not merge `main`.

## Execution record

- Existing linked worktree: `C:\Users\Jing_\.codex\worktrees\gnss-cir\GNSS_Multipath_Project`, branch `review/gnss-mainline-cir-model-20261022`, baseline HEAD `fbda48306134609c17963b1f4c642890ae1b2fc5`.
- Existing V0 targeted baseline: `python -m unittest scripts.channel_modeling.tests.test_mainline_stage2_v0 -v` → 18/18 PASS.
- Task 5: read-only current-state verification completed before WP2 implementation; details will be recorded after the final WP2 results are independently recounted.
