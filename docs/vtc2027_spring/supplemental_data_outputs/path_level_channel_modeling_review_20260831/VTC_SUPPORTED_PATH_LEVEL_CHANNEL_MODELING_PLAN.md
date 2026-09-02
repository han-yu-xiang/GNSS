# VTC Supported Path-Level Channel Modeling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and independently check the channel-modeling results that are supported by the current extracted path-observation table, without using raw IQ, MATLAB/SAGE, full CIR, DMC, or changing the formal manuscript.

**Architecture:** Use the existing primary path-observation population as a read-only source. Fit a two-dimensional delay-Doppler distribution for each environment-elevation cell, fit a separate one-dimensional distribution to path relative power, and derive a clearly labeled retained-path delay-dispersion ECDF from unique run-window path sets. Use the measured three-dimensional delay-Doppler-power scatter only as a visualization; power is not included in the first two-dimensional density model.

**Tech Stack:** Existing project Python environment at `D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe`, pandas, NumPy, SciPy, scikit-learn or the existing weighted-mixture implementation, Matplotlib, pytest, JSON/CSV/Markdown, and the existing Poppler tools for figure inspection.

**Spec:** Current user request; `E:\GNSS_Multipath_Project\docs\vtc2027_spring\VTC_PLAN.md`; `E:\GNSS_Multipath_Project\docs\vtc2027_spring\EVIDENCE_MATRIX.md`; and the read-only population and QA files in the current conditional-model review namespace.

## Global Constraints

- All new outputs remain below `E:\GNSS_Multipath_Project\docs\vtc2027_spring\supplemental_data_outputs\path_level_channel_modeling_review_20260831\`.
- The source CSV, canonical manuscript, canonical figures, canonical tables, Evidence Matrix, and handoff files are read-only during this plan.
- Use only rows with `primary_population_included=true`; use `cell_ready=true` for environment-elevation results.
- The primary environment classes are exactly `Urban` and `Mountain/Valley`; elevation bands are `LOW`, `MID`, and `HIGH`.
- The six cell counts are fixed by the current source: Urban/LOW 18, Urban/MID 169, Urban/HIGH 129, Mountain/Valley/LOW 22, Mountain/Valley/MID 117, and Mountain/Valley/HIGH 32.
- The six-cell population contains 487 rows and excludes 31 rows with missing elevation; no elevation imputation is allowed.
- The source contains 236 tracks, 518 primary path observations in total, 290 environment-only run-window groups, and 279 run-window groups after the elevation-ready filter.
- `absolute_doppler_hz` is the primary modeling Doppler variable; signed `doppler_offset_hz` is retained only for a directional visualization.
- A row is called a retained or persistent path observation in all paper-facing preview text; it is not called a confirmed physical path.
- The outputs are path-level statistical evidence, not a complete PDP, fading-envelope model, occurrence-rate model, path-lifetime model, or complete stochastic channel model.
- Do not calculate or claim full CIR PDP, Rayleigh/Rician/Nakagami envelope fitting, snapshot-lag correlation, RMS delay spread of the complete channel, Doppler spread, or Ricean K-factor.
- No SAGE, MATLAB, raw-IQ loading, MAT signal-payload loading, new experiment, Stage4 promotion, or manuscript synchronization is part of this plan.

---

### Task 1: Create the isolated input audit and fixed data contract

**Files:**
- Create: `scripts/audit_path_level_inputs.py`
- Create: `tests/test_path_level_inputs.py`
- Create: `qa/input_audit.json`
- Create: `qa/input_audit_report.md`
- Create: `README.md`

**Inputs:**
- `E:\GNSS_Multipath_Project\docs\vtc2027_spring\supplemental_data_outputs\urban_mountain_stage3_elevation_model_review_v3_conditional_gmm\population\gmm_feature_population.csv`
- Its existing population manifest and independent QA report.

**Interfaces:**
- `load_primary_population(path: Path) -> pandas.DataFrame`
- `audit_population(frame: pandas.DataFrame) -> dict`
- The audit result records source SHA-256, row counts, cell counts, track-weight sums, missing-elevation count, finite-value checks, and the exact field definitions used later.

- [ ] Verify the 518-row primary population and the 487-row elevation-ready subset.
- [ ] Verify the six cell counts listed in the global constraints.
- [ ] Verify every `track_weight_recomputed_primary` value is finite and the 236 track totals equal one within `1e-9`.
- [ ] Verify that each environment-elevation cell has at least two source scenes before scene-grouped validation is attempted.
- [ ] Verify that the modeling columns are `excess_delay_samples`, `absolute_doppler_hz`, and `relative_power_db`, and that the signed field is `doppler_offset_hz`.
- [ ] Write a report stating that the population contains retained path observations and that the 31 missing-elevation rows are excluded without imputation.
- [ ] Test that the audit fails if a required field is missing, a non-finite value is introduced, or any track weight total differs from one by more than `1e-9`.

### Task 2: Fit the two-dimensional delay-Doppler model

**Files:**
- Create: `scripts/fit_delay_doppler_2d.py`
- Create: `tests/test_delay_doppler_2d.py`
- Create: `model/delay_doppler_2d_candidates.csv`
- Create: `model/selected_delay_doppler_2d_models.json`
- Create: `model/delay_doppler_cell_summary.csv`

**Interfaces:**
- `fit_cell_models(frame: pandas.DataFrame, cell_id: str) -> list[dict]`
- `select_cell_model(candidates: list[dict]) -> dict`
- `predict_log_density(model: dict, xy: numpy.ndarray) -> numpy.ndarray`
- The model input is standardized `[Δtau_samples, |Delta f|_Hz]`; all stored means and covariance matrices are converted back to samples and Hz.

- [ ] Fit one-, two-, and three-component full-covariance Gaussian mixtures separately in each of the six cells.
- [ ] Apply the existing track weights during fitting and verify that the component covariance matrices are finite and positive definite.
- [ ] Use scene-grouped validation within each cell; score held-out weighted log density and retain BIC as a complexity check.
- [ ] Reject a candidate when a component has fewer than five effective observations, when validation is not finite, or when its covariance is not positive definite.
- [ ] Select the lowest-scoring valid model using held-out log density first and BIC as the tie-breaker; record the selected component count only in internal outputs.
- [ ] Produce a sensitivity fit using signed Doppler solely to show whether the observed cloud is approximately symmetric; do not use it as the primary model unless explicitly approved later.
- [ ] Test one synthetic two-cluster input with a known covariance and verify that the fitted density is finite and that the recovered means are in the correct physical coordinate system.

### Task 3: Fit the one-dimensional path-relative-power distribution

**Files:**
- Create: `scripts/fit_relative_power_models.py`
- Create: `tests/test_relative_power_models.py`
- Create: `model/relative_power_candidates.csv`
- Create: `model/selected_relative_power_models.json`
- Create: `model/relative_power_cell_summary.csv`

**Interfaces:**
- `fit_power_candidates(values: numpy.ndarray, weights: numpy.ndarray) -> list[dict]`
- `select_power_model(candidates: list[dict]) -> dict`
- `evaluate_power_pdf(model: dict, x_db: numpy.ndarray) -> numpy.ndarray`

- [ ] Treat `relative_power_db` as path-relative power, not as a received fading envelope.
- [ ] Compare a single Gaussian in dB, a two-component Gaussian mixture in dB, and a Beta model for the linear power ratio when the cell support is valid.
- [ ] Use weighted empirical CDF distance, held-out weighted log likelihood, and BIC to select a model; keep all candidate scores for review.
- [ ] Limit the number of mixture components using effective sample size and reject any component with fewer than five effective observations.
- [ ] Store fitted parameters in dB or linear-power units with explicit units and transformation formulas.
- [ ] Test PDF normalization numerically and verify that generated linear power ratios remain in the physical interval `(0, 1]` after inverse transformation.
- [ ] Ensure all figure and table labels use “path-relative power distribution” and never “Rayleigh/Rician fading envelope” for this result.

### Task 4: Derive the retained-path delay-dispersion ECDF

**Files:**
- Create: `scripts/derive_retained_path_delay_dispersion.py`
- Create: `tests/test_retained_path_delay_dispersion.py`
- Create: `model/retained_path_delay_dispersion.csv`
- Create: `model/retained_path_delay_dispersion_summary.csv`

**Interfaces:**
- `group_path_sets(frame: pandas.DataFrame) -> pandas.DataFrame`
- `compute_path_set_delay_dispersion(group: pandas.DataFrame) -> dict`
- `weighted_ecdf(values: numpy.ndarray, weights: numpy.ndarray) -> tuple[numpy.ndarray, numpy.ndarray]`

- [ ] Group rows by `run_id` and `center_window_id` and verify that each group has one environment and one elevation band.
- [ ] For each group, add the direct-path reference `(delay=0 samples, power=0 dB)` because all secondary powers are normalized to the direct path.
- [ ] Convert each relative power from dB to linear power and calculate the power-weighted mean delay and RMS delay dispersion in samples.
- [ ] Use the unique run-window group once, even when it contains two or three retained path observations; do not count a multi-path group multiple times.
- [ ] Produce 290 environment-only group values and 279 elevation-ready group values, with exact Urban/Mountain/Valley and six-cell counts recorded in the summary.
- [ ] Provide an unweighted empirical CDF as the primary descriptive plot and a track-balanced sensitivity CDF in the QA package; do not present either as the full-channel RMS delay spread.
- [ ] Test the formula on a direct-only group (dispersion zero) and a two-component group with analytically known weighted dispersion.

### Task 5: Generate the review figures and tables

**Files:**
- Create: `scripts/generate_path_level_model_figures.py`
- Create: `figures/delay_doppler_2d_environment_elevation.png`
- Create: `figures/delay_doppler_2d_environment_elevation.pdf`
- Create: `figures/relative_power_empirical_vs_fitted.pdf`
- Create: `figures/retained_path_delay_dispersion_ecdf.pdf`
- Create: `figures/delay_doppler_power_3d_signed.pdf`
- Create: `tables/delay_doppler_model_summary.csv`
- Create: `tables/relative_power_model_summary.csv`
- Create: `tables/retained_path_delay_dispersion_quantiles.csv`

- [ ] Plot the measured two-dimensional delay-Doppler observations and selected-model contours, with Urban and Mountain/Valley separated and LOW/MID/HIGH indicated consistently.
- [ ] Plot measured path-relative-power histograms or weighted empirical densities with the selected one-dimensional PDFs.
- [ ] Plot the retained-path delay-dispersion ECDF for the two environments and, in a separate panel or line style, the six environment-elevation cells.
- [ ] Keep the existing three-dimensional preview as a measured scatter: x is excess delay, y is signed relative Doppler, and z/color is relative power. Do not draw a fitted surface unless a later plan explicitly defines one.
- [ ] Use English scientific labels in figures intended for the manuscript and Chinese explanatory notes only in the review README.
- [ ] Write tables with sample counts, effective track counts, selected model family, fitted parameters, and fit scores; omit internal pooling terminology from paper-facing table labels.
- [ ] Render every PDF figure to PNG and inspect axes, legends, contours, units, and panel spacing before declaring the preview usable.

### Task 6: Independent QA and stop-for-review package

**Files:**
- Create: `qa/model_qa.json`
- Create: `qa/model_qa_report.md`
- Create: `qa/source_integrity_before_after.json`
- Modify: `README.md` only within the isolated output namespace

- [ ] Recompute all row counts, cell counts, group counts, finite-value checks, covariance eigenvalues, PDF normalization checks, and dispersion formula checks independently of the fitting scripts.
- [ ] Confirm no source CSV, canonical Figure 1-4, canonical table, manuscript `.tex`/`.pdf`, Evidence Matrix, or handoff file changed during execution.
- [ ] Confirm no raw IQ, MAT signal payload, MATLAB, SAGE, Stage4, or new experiment was used.
- [ ] Mark the following as not produced by this plan: true PDP, received fading-envelope fit, full-channel RMS delay spread, snapshot-lag correlation, Doppler spread, Ricean K-factor, occurrence rate, and complete stochastic channel generator.
- [ ] Write a short interpretation section that distinguishes the two-dimensional density, path-relative-power marginal, and retained-path delay-dispersion ECDF.
- [ ] Stop and wait for author review. Do not modify the manuscript or synchronize handoffs after QA; that requires a separate approved plan.

## Acceptance Criteria

- The six-cell two-dimensional delay-Doppler models have finite validation scores and positive-definite covariances, or a cell is explicitly marked empirical-only when no candidate passes the predefined checks.
- Every selected power model has a normalized PDF and an explicit parameter transformation.
- The delay-dispersion ECDF has exactly 290 environment-only and 279 elevation-ready unique run-window groups, with 31 missing-elevation rows excluded.
- All plots are readable after rendering and contain no unsupported claim such as “full PDP,” “fading envelope,” “complete channel model,” or “confirmed physical path.”
- The canonical manuscript and all canonical scientific artifacts are byte-for-byte unchanged.
- The output namespace contains the plots, tables, model files, QA files, source provenance, and this plan only; no output is copied into the formal manuscript directory.

## Review Decision After Completion

The author reviews the figures and tables first. If the two-dimensional model and path-level statistics are scientifically clear, a separate manuscript-integration plan will specify the exact section, equations, captions, and bilingual synchronization. If the results are not sufficiently clear, retain them as supplemental analysis and leave the frozen manuscript unchanged.
