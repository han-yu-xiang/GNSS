# Mainline Stage2 WP6 Joint Channel Model Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fit and validate a reproducible Stage2-selected-window count-and-mark model, compare independent and Gaussian-copula path marks on whole held-out scenes, and separately test SAGE-derived delay summaries against accepted CIR/PDP window features.

**Architecture:** Add one focused WP6 Python module that reuses WP3 family fitting and scene/window weights, plus a runner and a separate output validator. Read only the two frozen WP4 CSVs; write a new timestamped result package, then sync the authoritative plan and handoffs.

**Tech Stack:** Python 3.12, NumPy, pandas, SciPy, matplotlib, stdlib `unittest`; no new dependency. The current Python has no pytest module.

**Spec:** `docs/superpowers/specs/2026-10-29-mainline-stage2-wp6-joint-channel-model-design.md`

## Global Constraints

- Pin `stage2_cir_pdp_window_features.csv` SHA-256 `258d5d70081d9ee6fd82a64b1a4f9c405180bc18cd49280b0e2b799d9a482bf4` and `stage2_mpc_cir_alpha_linkage.csv` SHA-256 `8db941db20e684108d13583d67ee20cde543bf2a36ca01013d1288b48231c80b`.
- The population is conditional on Stage2 selection: retain all 7,847 selected windows (including zero-MPC rows) and 8,914 MPCs; never assign zero MPC to an unselected Stage0 window.
- Use complete-scene outer LOSO across 13 scenes. Inner family selection, fitting, copula estimation, scaling, and missingness choices must exclude the outer scene.
- Reuse WP3's candidate families, `_fit_static`, `_distribution_logpdf`, `scene_window_weights`, and `make_scene_folds`; retain failed and unsupported fits rather than silently dropping them.
- Fit scene-balanced count probabilities from training scenes only; use `{0,1,2,3}` as the observed support and do not smooth unseen categories.
- Treat a selected-window mark set as exchangeable; conditional iid generation given count is an explicit simplifying assumption, not established within-window physics. Do not treat MPC rows, overlapping windows, or LOSO folds as independent scene replicates.
- Keep CIR/PDP as separate window-level responses; retain and flag all 63 boundary-peak windows. Do not call the shared-input CIR/PDP comparison external propagation truth or infer physical RMS delay spread.
- Do not reuse Stage3 r3 or WP3 environment parameters, add an environment/elevation primary model, use alpha phase for cross-window evolution, or start Phase-2 generative AI.
- Do not rerun SAGE, CIR, or alpha export, mutate frozen tables, overwrite existing outputs, or stage unrelated pre-existing untracked files.
- Keep WP6 outputs in one new timestamped directory under `reports/data_consolidation_20261003/mainline_1023_model_v1/`; Git stages only WP6 code, tests, report, compact tables/figures and synchronized docs, not source payloads.

## Review Focus

1. A count category missing in a training/test fold must be recorded as unsupported, not assigned a smoothed probability; test with a deliberately absent category.
2. Positive-support marginal failures, nonfinite observations, and boundary/optimizer failures must remain visible and must not win family selection; test invalid support and failed fits.
3. Copula PIT clipping and a non-positive-definite scene-balanced correlation matrix must be deterministic and recorded; test independence, singularity and projection behavior.
4. Exact window/path joins must retain every frozen key and all zero-MPC selected windows; test duplicates, missing/extra paths and zero-count windows.
5. PDP boundary flags and zero-MPC windows must survive scene-held-out prediction, with all response transforms and coefficients learned from training scenes only; test fold leakage and retained boundary rows.

---

### Task 1: Pinned population contract and selected-window count model

**Files:**
- Create: `scripts/channel_modeling/mainline_stage2_wp6.py`
- Create: `scripts/channel_modeling/tests/test_mainline_stage2_wp6.py`
- Include the approved WP6 design spec and this plan in the first WP6 commit; do not stage other untracked files.

**Interfaces:**
- `load_wp6_inputs(features_path, mpc_path, expected_hashes=...) -> (windows, mpcs, input_manifest)` verifies bytes, schemas, canonical unique keys and the exact one-to-many window linkage.
- `validate_wp6_population(windows, mpcs, expected_contract=None) -> None` requires 7,847 unique windows, 8,914 unique MPC keys, consistent per-window counts and 13 scenes for the frozen production run; tests pass an explicit fixture contract.
- `fit_count_probabilities(training_windows) -> dict[int, float]` averages per-scene category frequencies equally using training scenes only; `score_count_fold(...)` returns per-window and per-scene count log scores and an explicit unsupported-category status.
- `scene_window_weights` and family utilities are imported from `mainline_stage2_wp3.py`, not reimplemented.

- [x] **Step 1: Write failing tests** named `test_pinned_schema_and_exact_window_path_keys_reconcile`, `test_zero_mpc_selected_windows_remain_in_the_count_denominator`, `test_duplicate_missing_extra_and_inconsistent_count_keys_fail`, `test_scene_macro_count_probabilities_use_training_scenes_only`, and `test_unsupported_count_category_is_not_smoothed`; assert exact frozen dimensions in production mode and exact hand-computed fixture results in unit mode. Load the not-yet-created module dynamically and assert the missing API with `self.assertTrue(callable(...))`, so RED is an assertion failure rather than a collection/import error.
- [x] **Step 2: Run RED**: `python -m unittest discover -s scripts/channel_modeling/tests -p test_mainline_stage2_wp6.py -v`; expected: failing assertions for the absent WP6 API, no import/collection errors.
- [x] **Step 3: Implement only the input contract and count functions** in `mainline_stage2_wp6.py` using the fixed production pins and existing project identity conventions.
- [x] **Step 4: Run GREEN**: repeat the focused unittest discovery command; require every named test to pass.
- [x] **Step 5: Commit** only the WP6 spec, plan, module, and test file with message `feat: add WP6 input contract and selected-window count baseline`.

### Task 2: Nested scene-LOSO marginal and copula mark model

**Files:**
- Modify: `scripts/channel_modeling/mainline_stage2_wp6.py`
- Test: `scripts/channel_modeling/tests/test_mainline_stage2_wp6.py`

**Interfaces:**
- `select_mark_families_nested(mpcs, outer_training_scenes) -> (families, inner_scores, failures)` performs inner complete-scene LOSO separately for delay, Doppler, and power, then refits selected families on all outer-training scenes.
- `fit_scene_balanced_copula(training_mpcs, fitted_marginals) -> (correlation, diagnostics)` estimates pairwise dependence within scenes only, uses the approved Kendall-to-Gaussian transform and records any positive-definite projection.
- `score_mark_models(fitted, copula, test_mpcs) -> per-window/per-scene scores` reports product-marginal and copula mark scores; window score sums path log densities under the conditional-iid mark likelihood, then scene summaries macro-average selected windows.
- `calibrate_mark_tails(fit, heldout_mpcs, quantiles=(.01,.05,.10,.90,.95,.99)) -> tail rows` compares training-predicted and held-out empirical quantiles/coverage; expected tail support below 10 is `LOW_SUPPORT`, retained rather than passed or dropped.
- `evaluate_nested_mark_loso(mpcs, scenes) -> fold, parameter, failure, and tail tables` emits all 13 outer scenes, inner-family evidence, parameters, support and fit failures.
- `fit_final_mark_model(mpcs) -> final families, parameters, dependence` uses inner LOSO over all 13 scenes for family choice and then refits on the full population; these parameters are descriptive deployment candidates, not out-of-scene evidence.

- [x] **Step 1: Add failing tests** named `test_inner_loso_never_uses_outer_scene_for_family_selection`, `test_mark_fit_reuses_wp3_families_and_window_scene_weights`, `test_identity_copula_matches_product_marginal_density`, `test_copula_log_density_matches_hand_calculation`, `test_scene_balanced_kendall_and_projection_are_recorded`, `test_mark_scores_pair_identical_heldout_keys_and_sum_within_window`, `test_tail_quantiles_use_train_fit_and_flag_expected_support_below_ten`, and `test_fit_failures_remain_visible_and_final_refit_is_separate`.
- [x] **Step 2: Run RED**: `python -m unittest discover -s scripts/channel_modeling/tests -p test_mainline_stage2_wp6.py -v`.
- [x] **Step 3: Implement the nested LOSO, Gaussian-copula and mark-score functions**; do not add family candidates or inferential path-level confidence intervals.
- [x] **Step 4: Run GREEN**: repeat focused unittest discovery and require all Task 1/2 tests to pass.
- [x] **Step 5: Commit** code/tests with message `feat: add nested scene-held-out WP6 marked model`.

### Task 3: Separate SAGE-summary to CIR/PDP scene-held-out tests

**Files:**
- Modify: `scripts/channel_modeling/mainline_stage2_wp6.py`
- Test: `scripts/channel_modeling/tests/test_mainline_stage2_wp6.py`

**Interfaces:**
- `derive_window_delay_summaries(windows, mpcs) -> windows_with_summaries` computes relative-power-weighted centroid and RMS spread, including a unit-weight direct reference at zero delay, and retains every selected window.
- `evaluate_cir_pdp_loso(windows_with_summaries, scene_folds) -> prediction_rows, scene_scores` compares training-scene intercept baselines with one-predictor linear models for the two frozen WP6 pairs; all fits and transforms use training scenes only.

- [x] **Step 1: Add failing tests** named `test_weighted_delay_moments_include_unit_direct_reference`, `test_zero_mpc_window_is_retained_with_direct_only_moments`, `test_all_window_keys_and_boundary_flags_survive`, `test_pdp_regression_uses_only_training_scenes`, `test_scene_macro_mae_rmse_are_hand_computable`, and `test_duplicate_keys_and_invalid_pdp_responses_fail_closed`.
- [x] **Step 2: Run RED**: `python -m unittest discover -s scripts/channel_modeling/tests -p test_mainline_stage2_wp6.py -v`.
- [x] **Step 3: Implement the two specified SAGE-to-PDP association tests only**; do not feed PDP into mark fitting or use alpha phase.
- [x] **Step 4: Run GREEN**: repeat focused unittest discovery and require all Task 1–3 tests to pass.
- [x] **Step 5: Include** the code/tests in the final WP6-only delivery commit; no duplicate Task 3 commit was created.

### Task 4: Reproducible runner, independent validator and result package

**Files:**
- Create: `scripts/channel_modeling/run_mainline_stage2_wp6.py`
- Create: `scripts/channel_modeling/validate_mainline_stage2_wp6.py`
- Modify: `scripts/channel_modeling/tests/test_mainline_stage2_wp6.py`
- Generate: one new `reports/data_consolidation_20261003/mainline_1023_model_v1/wp6_<UTC timestamp>/` result package.

**Interfaces:**
- Runner CLI accepts the two frozen CSV paths and a create-new output directory; production mode enforces the fixed pins and verifies the executing code root.
- Runner writes an input/code manifest, fold and parameter tables, count and mark scores, CIR/PDP predictions, compact summaries, figures, execution/test logs, and the Chinese formal report. It refuses an existing output directory.
- The independent validator reads source/output files without importing WP6 fitting/scoring functions; it checks hashes, exact key/count reconciliation, fold isolation, finite parameters, preserved failure/boundary records and independently recomputes count and window-delay summary arithmetic.

- [x] **Step 1: Add runner/validator tests** using isolated temporary fixtures and verify the production inputs are not written.
- [x] **Step 2: Run RED** for the initial missing runner/validator API and behavioral assertions.
- [x] **Step 3: Implement** the minimal runner, independent checks, figures and report generation.
- [x] **Step 4: Run GREEN**; the final focused WP6 suite passes 33/33 and the independent validator passes on the saved real-data package.
- [x] **Step 5: Include** runner/validator/tests in the final WP6-only delivery commit; no separate Task 4 commit was created.

### Task 5: Execute real scene-held-out analysis, independent review and handoff

**Files:**
- Generate under the new result directory: all WP6 fold, parameter, per-window/per-scene scores and predictions, manifest, figures, execution record, Chinese report and independent validation record.
- Modify: `docs/ACADEMIC_CHANNEL_MODELING_MASTER_PLAN.md`
- Modify: `docs/GNSS_SAGE_ENGINEERING_HANDOFF_CURRENT.md`
- Modify: `docs/GNSS_SAGE_PAPER_HANDOFF_CURRENT.md`

- [x] **Step 1: Run the WP6 CLI** on both SHA-pinned WP4 CSVs into the new result directory; preserve the original failed assembly attempt and the successful run record.
- [x] **Step 2: Run and extend independent validation**; reconcile identities/counts/delay arithmetic and independently recompute all 52 scene/model/target PDP score rows and macro summaries.
- [x] **Step 3: Obtain an independent scientific/code review**; correct the count-scene key binding and PDP score-validation gaps test-first. Copula continuous scoring with quantized/tied delay is disqualified from model ranking; keep its raw output as diagnostics only.
- [x] **Step 4: Update** the master plan and engineering/paper handoffs with actual status, results, limitations, tests, review, and one next decision; Gate G remains pending.
- [x] **Step 5: Verify** focused WP6 tests 33/33, full channel-modeling tests 216/216, `py_compile`, pinned inputs, enhanced validator, and result-relative links; final diff/Git checks remain part of final delivery.
- [x] **Step 6: Stage only WP6-specific files**, commit the final WP6 study, push normally to `origin/review/gnss-mainline-cir-model-20261022`, update Draft PR #2 without merging, and verify remote HEAD and PR state.

### Scientific review disposition (2026-10-29)

- Count results remain conditional on Stage2-selected windows. The empirical count table is retained; 277,905 unselected Stage0 windows are not assigned zero MPC.
- Nested scene-LOSO supports delay Lognormal in 13/13 outer folds and Doppler Student-t in 13/13; relative-power family selection is unstable (Student-t 8/13, Normal 5/13).
- The current delay variable is quantized/tied (128 unique stored floating values; 127 at 0.01 chip). Continuous Gaussian-Copula point-density scores and the tau-b to continuous-Gaussian transform do not provide a valid mixed-data proper likelihood here. Existing Copula score deltas are diagnostics, not evidence for gain or no gain; no ties-aware replacement was fitted.
- Count and mark components form only a factorized candidate. Count-conditional mark invariance/exchangeability and conditional-iid generation are unverified; do not call it a validated full joint generator.
- PDP scene-LOSO associations are separate, shared-input code-domain association checks, not independent propagation truth. Gate G remains `PENDING`; no Phase-2 or production computation is authorized by this plan.
- Final review also added a regression for an unscorable held-out scene with multiple MPCs per window. The previous failure path incorrectly merged path-level rows as unique windows and raised `MergeError`; the code now deduplicates window identities and preserves path counts. The actual 13 outer folds were all scoreable, so no saved model output was recomputed. The RED failure was observed interactively but its terminal transcript was not separately persisted; the final 33/33 and 216/216 green logs are preserved.

### Task 6: Close independent-review findings on joint scoring and retained diagnostics

**Files:**
- Modify: `scripts/channel_modeling/mainline_stage2_wp6.py`
- Modify: `scripts/channel_modeling/run_mainline_stage2_wp6.py`
- Modify: `scripts/channel_modeling/validate_mainline_stage2_wp6.py`
- Test: `scripts/channel_modeling/tests/test_mainline_stage2_wp6.py`
- Generate: one new timestamped WP6 result directory; preserve the existing package.
- Modify: WP6 report, master plan, engineering and paper handoffs.

**Review findings verified against the approved spec:** the result package must report count and mark scores separately and jointly; a missing Copula estimate must not discard usable product-marginal scores; and retained fit-failure/low-support tail diagnostics must be reconciled by the independent validator.

- [x] **Step 1: Add isolated regressions** for count-mark window coverage, Copula-unavailable product scoring, failure/tail reconciliation, and a positive manifest-row-count corruption. The earlier missing-output behavior was identified during review; no separate standalone RED transcript was retained.
- [x] **Step 2: Implement minimal product-only scoring** so valid fitted marginals remain scored when the scene-balanced Copula is unavailable, with Copula availability represented separately.
- [x] **Step 3: Implement the selected-window factorized count + product-mark score**: exactly one row per Stage2-selected window, count log score plus the sum of path mark product log densities, empty mark contribution 0 for selected zero-MPC windows, and scene-equal macro summaries. Do not create a Copula joint score because tied/quantized delay invalidates the current continuous Copula point-density comparison.
- [x] **Step 4: Independently reconcile retained mark failures and tail-support records** against the nested inner-family and outer-fold tables, including exact expected key/support counts and summary totals; retain low-support rows rather than filtering them.
- [x] **Step 5: Run focused tests, rerun real analysis into a new create-only output directory, independently validate the new package, and update reports/provenance and authoritative docs.** Final package is `wp6_20261029T154500Z_final/`; earlier packages remain unchanged.
- [x] **Step 6: Run the complete channel-modeling suite and compile checks, request one fresh-context whole-branch review, address findings, then stage only WP6 files, commit, push normally, update Draft PR #2 and verify the remote/PR.** Full channel-modeling suite 222/222, compile and diff checks passed; independent review findings are closed. Commit `d4770a36efadefddba4533fb8fd6f9a25b799e48` was pushed normally, PR #2 was updated and remains Draft/unmerged. Final remote/PR verification follows the delivery record below.

## Final Git/PR delivery record

- 2026-10-30: WP6 implementation, final result package, validation evidence and synchronized plans/handoffs committed as `d4770a36efadefddba4533fb8fd6f9a25b799e48` (`feat: complete WP6 joint channel model study`) and pushed normally to `origin/review/gnss-mainline-cir-model-20261022`.
- Existing Draft PR #2 description now contains a WP6 section that supersedes the earlier pending-status text. It remains open, Draft, targets `main`, and is not merged.
- Only WP6 source, evidence, final and reviewed analysis packages, and the four WP6/authoritative-document paths were included. Other work-package files remain untouched and unstaged.

### Final review closure (2026-10-29)

- Independent reviewer follow-up after the final changes found no Critical, Important, or Minor findings. Earlier minor issues are closed: all PNG labels are readable English; the Copula figure itself identifies the values as diagnostic-only and explains the tied-delay limitation; and a positive row-count corruption regression verifies the existing end-to-end exact-row check.
- Final WP6 focused tests are 39/39 PASS; full channel-modeling suite 222/222 PASS; Python compilation exit 0. Independent validation is `PASS_WITH_LIMITATIONS`, 7,847 windows / 8,914 MPC, 52/52 PDP score rows, 13/13 joint-scored scenes, with all 6 fit failures and 72/234 low-support tail rows retained.
- The final rerun took 264.404 seconds. Portable code/input identities, validation summary, exact commands, timestamps, and logs are in `reports/data_consolidation_20261003/mainline_1023_model_v1/wp6_20261029T154500Z_final/`. WP6 remains `COMPLETED_WITH_LIMITATIONS`, Gate G `PENDING`; no production work or Phase-2 was started.

## Task Interfaces / Pre-flight

- Task 1 produces the validated selected-window and MPC frames plus count scores consumed by Tasks 2–4.
- Task 2 consumes Task 1's exact keyed MPC frame and produces nested mark model/fold tables; Task 4 serializes these outputs.
- Task 3 consumes Task 1's exact window/path frames and Task 2's independent model is not an input; Task 4 serializes these outputs separately.
- Task 4 consumes all three analytical interfaces; Task 5 consumes only its validated result package and performs scientific review/document synchronization.
- No preflight interface conflict: all consumers preserve `(run_id,window_id)` or `(run_id,window_id,path_id)` identities and retain the frozen conditional denominator.

## Final Review Focus

- Check for held-out scene leakage in every nested fit, copula estimate, scaling step, and PDP model.
- Check score definitions and sample pairing are identical between independent and copula alternatives.
- Check count probabilities are conditional on Stage2 selection and preserve zero-MPC selected windows without treating unselected Stage0 windows as zero.
- Check copula PSD projection, path clustering, overlapping windows, and conditional-iid limitations remain explicit.
- Check the shared-input CIR/PDP association is not presented as independent truth or a physical channel reconstruction, and all 63 boundary peaks remain.
