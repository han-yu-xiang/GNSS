# Gate G Fixed-Bin Doppler Score Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Evaluate fixed-bin Stage2 Doppler marginal and delay–Doppler–power dependence with a proper mixed-measure score under 13-scene nested LOSO.

**Architecture:** Add an isolated fixed-bin analysis module and runner that reuse frozen WP6 input loading, delay/power marginal fitting, and Stage2 identity preparation. Keep the existing adaptive-Doppler Gate G outputs immutable. Use deterministic Gaussian rectangle integration for two discrete latent intervals conditional on continuous power; compare the independent and Copula models on identical held-out paths/windows.

**Tech Stack:** Python, NumPy, pandas, SciPy, unittest; frozen WP4 light CSV inputs only.

**Spec:** `docs/superpowers/specs/2026-10-30-gateg-fixed-doppler-bin-score-design.md`

## Global Constraints

- Fixed Doppler bins are centered at 0 Hz with half-open edges `(k+1/2)w`; primary width is 5 Hz and 10/20 Hz are predeclared sensitivity analyses.
- Delay and Doppler are scored as interval probabilities; relative power is scored as a continuous density.
- All family fitting and selection use training scenes only; outer evaluation is complete 13-scene LOSO.
- Do not infer bins from held-out values, alter frozen inputs, or claim exact likelihood for the adaptive SAGE estimator.
- Do not rerun SAGE/CIR/alpha or read MAT/HDF5/raw-IQ payloads.
- Preserve all existing files and unrelated untracked work; no main merge.

## Review Focus

- Exact half-open tie assignment at positive and negative Doppler edges — test both edge signs and adjacent floating-point values.
- Discrete family mass normalization and tail-stable log probabilities — test Normal/Student-t over a broad complete bin partition.
- Mixed Copula normalization and identity reduction — compare with independent quadrature and sum a complete two-bin partition conditional on power.
- Fold leakage and unequal support — assert each selected family records only outer-training scenes and M0/C0 path/window identities are exactly paired.
- Non-finite/near-singular numerical inputs — reject malformed correlation matrices and preserve explicit failed-fold records rather than silently dropping rows.

---

### Task 1: Fixed Doppler cells and grouped marginal likelihood

**Files:**
- Create: `scripts/channel_modeling/mainline_stage2_wp6_fixed_doppler.py`
- Test: `scripts/channel_modeling/tests/test_mainline_stage2_wp6_fixed_doppler.py`

**Interfaces:**
- Consumes existing `mainline_stage2_wp6_gateg` delay-grid/family utilities, `mainline_stage2_wp6` frozen constants, and `mainline_stage2_wp3.scene_window_weights`.
- Produces `doppler_bin_indices(values, width)`, `doppler_bin_cells(indices, width)`, `doppler_bin_log_mass(family, values, width, parameters)`, and `fit_doppler_bins(frame, family, width)`.

- [x] Write tests for 0-centered half-open bins, exact +/- half-bin ties, adjacent floats, invalid widths, all-bin probability normalization, and grouped-fit recovery on synthetic Normal and Student-t samples.
- [x] Run the new test file and confirm expected RED failures because the fixed-bin API is absent.
- [x] Implement the bin and grouped-likelihood APIs; use scene/window-balanced weights and keep fitted parameters/status explicit.
- [x] Re-run the focused tests and the pre-existing Gate G focused tests; record the real command and counts.

### Task 2: Two-discrete/one-continuous Gaussian Copula score

**Files:**
- Modify: `scripts/channel_modeling/mainline_stage2_wp6_fixed_doppler.py`
- Test: `scripts/channel_modeling/tests/test_mainline_stage2_wp6_fixed_doppler.py`

**Interfaces:**
- Produces `normal_rectangle_log_probability(...)`, `fixed_bin_product_log_score(fits, frame, width)`, `fixed_bin_copula_log_score(fits, correlation, frame, width)`, and `fit_fixed_bin_copula(training_frame, fits, width)`.
- Mixed score is `log P(delay cell, Doppler bin, power interval)` where the two discrete latent-normal intervals are jointly integrated conditional on the power latent score; power contributes its continuous marginal density.

- [x] Add RED tests for identity-copula equality, bivariate rectangle agreement with independent `scipy.integrate.quad`, normalization over a complete rectangle partition conditional on several power values, continuous power density, and invalid/near-singular matrices.
- [x] Run tests to confirm they fail at the missing fixed-bin mixed-measure APIs.
- [x] Implement stable deterministic quadrature and training-only scene/window-balanced composite-likelihood fitting.
- [x] Run the new focused tests and pre-existing Gate G tests; inspect normalization and numerical error explicitly.

### Task 3: Nested scene-out evaluation and frozen-input execution

**Files:**
- Create: `scripts/channel_modeling/run_mainline_stage2_wp6_fixed_doppler.py`
- Test: `scripts/channel_modeling/tests/test_mainline_stage2_wp6_fixed_doppler.py`

**Interfaces:**
- Produces `evaluate_fixed_bin_loso(mpcs, widths=(5, 10, 20), expected_scenes=13, progress_callback=None)` and a CLI runner using `wp6.load_wp6_inputs` with the existing pinned feature/MPC SHA values.
- Primary comparison: 5 Hz M0 independent versus C0 Copula. Widths 10/20 Hz are sensitivity analyses, not chosen from held-out data. Doppler family selection is nested within outer training scenes; delay and power use the existing nested selectors restricted to those variables.

- [x] Add RED tests for 13-scene fold isolation, no held-out scene in fitting/selection records, fixed widths/edges, complete paired support, and explicit fit failure reporting.
- [x] Confirm RED, then implement the 13-fold evaluator and versioned output runner. Write outputs only to a new directory.
- [x] Run focused synthetic tests, then run the real frozen-CSV evaluation once for 5/10/20 Hz; do not access large science payloads.
- [x] Save execution/input/code manifests, per-fold parameters and selection, path/window/scene scores, paired deltas, and a concise scientific report.

### Task 4: Independent validation, handoffs, and Git delivery

**Files:**
- Create: `scripts/channel_modeling/validate_mainline_stage2_wp6_fixed_doppler.py`
- Create: `reports/data_consolidation_20261003/mainline_1023_model_v1/wp6_gateg_fixed_doppler_bins_<run-id>/` (real run outputs)
- Modify: `docs/ACADEMIC_CHANNEL_MODELING_MASTER_PLAN.md`
- Modify: `docs/GNSS_SAGE_ENGINEERING_HANDOFF_CURRENT.md`
- Modify: `docs/GNSS_SAGE_PAPER_HANDOFF_CURRENT.md`
- Preserve and submit this approved spec and implementation plan.

- [x] Add validator checks for input hashes, 13 fold identities, nested training-scene provenance, unchanged held-out support, finite/failure accounting, paired score arithmetic, and independent quadrature recomputation on a deterministic stratified sample.
- [x] Execute the validator and record the full actual output and exit code in the new result package.
- [x] Conduct an independent scientific review of score validity, LOSO leakage, support, uncertainty limits, and claims; record Gate G recommendation without presuming passage.
- [x] Update all three authoritative documents and the Gate G report with actual results and limitations; run focused tests, validator, `git diff --check`, and review the exact change list.
- [x] Commit only relevant source, tests, result tables/reports, spec/plan, and handoffs; push to the existing research branch and update Draft PR #2 without merging main.
