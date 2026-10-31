# Mainline Stage2 WP6 Joint Statistical Channel Model — Design

## Intent

Build and evaluate a reproducible joint statistical description of the 83-run,
13-scene Mainline Stage2 population. The model is conditional on windows selected
by the frozen Stage1/Stage2 pipeline. It is meant to describe/generate selected-
window MPC counts and their measured path marks, then test whether those
SAGE-derived summaries predict accepted window-level code-domain CIR/PDP
features in unseen scenes. It is not an unconditional multipath occurrence
model or a calibrated physical-channel simulator.

The Commander selected the two-level selected-window count plus path-mark
copula route. This document fixes the scientific interfaces before code or
fitting begins.

## Evidence and frozen inputs

- WP4 final Gate E/F feature table:
  `reports/data_consolidation_20261003/mainline_1023_model_v1/wp4_gate_ef_final_20261029T181100/stage2_cir_pdp_window_features.csv`
  SHA-256 `258d5d70081d9ee6fd82a64b1a4f9c405180bc18cd49280b0e2b799d9a482bf4`;
  7,847 unique `(run_id, window_id)` rows.
- WP4 final Stage2-MPC/CIR/alpha linkage:
  `reports/data_consolidation_20261003/mainline_1023_model_v1/wp4_gate_ef_final_20261029T181100/stage2_mpc_cir_alpha_linkage.csv`
  SHA-256 `8db941db20e684108d13583d67ee20cde543bf2a36ca01013d1288b48231c80b`;
  8,914 unique `(run_id, window_id, path_id)` MPC rows.
- WP4 final summary binds cohort SHA-256
  `287e891fae0cd294a85c073080611a19b7389ece46240b89cb1d5dab4df90229`,
  Stage2 ledger SHA-256
  `bbb8cac8338194b5527e00812a6547129a58466cc5fdd7db36b8c44bba01e551`,
  and WP5 alpha ledger SHA-256
  `def2e1e249af309a5114c100d0630299ebd955cefef6e051407fecb68e5493d7`.
- WP1/WP2 establish the candidate families and conditional empirical count
  baseline; WP3 does not establish robust environment or elevation gains.
- WP4 Gate F verifies PDP as the mean of 40 CIR snapshot powers, while also
  documenting that CIR/PDP shares raw-IQ/Stage0 inputs with SAGE and is not an
  independent propagation truth measurement.

The two WP4 CSV hashes, row counts, keys, and all MPC-to-window links were
rechecked read-only on 2026-10-29 before this design. No MAT/HDF5/raw-IQ payload
was read for this design step.

## Goals

1. Preserve all 7,847 Stage2-selected windows, including selected windows with
   zero MPC, and all 8,914 MPC identities.
2. Define a compact generative model for `N_MPC` and the joint distribution of
   `(excess_delay_chips, doppler_offset_hz, relative_power_db)` conditional on
   `N_MPC > 0` and Stage2 selection.
3. Compare the product-marginal baseline with a Gaussian-copula dependence
   model under outer leave-one-scene-out (LOSO) validation.
4. Use the WP4 window table for a separate, scene-held-out predictive test of
   SAGE-derived weighted delay summaries against measured code-domain PDP
   features; do not feed CIR/PDP labels into path-model fitting.
5. Report per-scene outcomes and limitations without treating rows, paths,
   overlapping windows, or LOSO folds as independent scene replicates.
6. Preserve reproducible inputs, source hashes, outputs, failed fits, and an
   independent numerical/scientific review record.

## Non-goals and anti-goals

- No SAGE, CIR, or alpha re-export; no mutation of frozen data.
- No Stage0-wide occurrence model and no assignment of zero MPC to unselected
  windows.
- No transfer of Stage3 r3 or WP3 nine-scene fitted parameters into the
  13-scene Mainline fit.
- No mandatory environment/elevation hierarchy: WP3 found no stable M1 gain,
  only mixed M2 evidence, and sparse scene support; these remain limitations
  and exploratory context, not the primary WP6 model.
- No cross-window coherent alpha evolution, absolute channel gain, physical
  reflector tracking, or claim that CIR/PDP is external ground truth.
- No Phase-2 MDN/normalizing-flow implementation.

## Approaches

1. **Selected-window marked model (selected).** Empirical Stage2-selected
   window count plus path-level marginal marks, with independent-product and
   Gaussian-copula alternatives. It is generative at the level supported by
   the ledger and can be scored by whole scene.
2. **Window-aggregate-only model (not selected).** Jointly models count and
   window summaries but cannot generate path-level delay/Doppler/power.
3. **Environment/elevation-conditioned hierarchical generator (deferred).**
   More complex than supported by the prior WP3 scene-out results and
   covariate coverage; it risks unsupported group estimates and is not needed
   to answer the primary joint-dependence question.

## Proposed model

Let `S=1` denote a Stage2-selected window. For selected window `w`, let `N_w`
be its MPC count and let `X_wi=(tau_wi, nu_wi, p_wi)` be the excess delay in
chips, signed relative Doppler in Hz, and relative power in dB for MPC `i`.
Direct-reference paths are not MPC marks.

### Count component

Use a categorical empirical distribution on the observed support `{0,1,2,3}`:

`P(N_w=n | S=1) = pi_n`.

For each outer fold, estimate `pi_n` using the mean of the per-scene training
frequencies, so a scene with more selected windows does not dominate the
new-scene target. Retain the all-window pooled histogram as a descriptive
population statistic. No count model is defined for `S=0`.

### Path-mark component

For `N_w>0`, use a scene- and window-balanced composite mark model. Each
training scene receives equal total weight; within a scene each MPC-bearing
window receives equal weight; within a window its MPC rows share that window's
weight. The primary marginals are selected without access to the outer test
scene by inner complete-scene CV among the frozen WP1/WP3 candidate families:

- `tau`: Lognormal, Gamma, Weibull (positive support, `loc=0` where the
  existing accepted fitter fixes it);
- `nu`: Normal, Laplace, Student-t;
- `p`: Normal, Laplace, Student-t.

If an inner fit fails or reaches a non-finite/boundary solution, retain its
failure record and choose only among supported candidates. The selected family
is refit on the complete outer training scenes. Identical marginal families
and parameters feed both dependence alternatives for that fold.

The baseline is the product density:

`f_0(x) = product_j f_j(x_j)`.

The joint alternative is a Gaussian copula:

`f_1(x) = c_R(F_tau(tau), F_nu(nu), F_p(p)) * product_j f_j(x_j)`.

Estimate each pairwise Gaussian-copula correlation from within-scene Kendall
rank dependence in training scenes only, transform `tau_K` to `rho` by
`rho=sin(pi*tau_K/2)`, and average correlations equally across training scenes.
If the assembled matrix is not positive definite, apply and record the minimal
eigenvalue-floor projection and renormalize its diagonal to one. This is a
scene-balanced pseudo-likelihood dependence estimate, not path-independent
inference. Model-score differences are first summarized within each selected
window and then macro-averaged by scene; the count score and mark score are
reported separately and jointly. The within-window mark score is a composite
score for an exchangeable marked set, not a claim that MPC marks or overlapping
windows are independent. For generation conditional on count, the first
implementation treats the marks as exchangeable and conditionally iid draws
from the fitted copula mark distribution. That is a simplifying generative
assumption, not a fact established by marginal fits or pairwise rank
dependence; it does not preserve an empirically identified within-window
ordering or higher-order cluster structure. The validation will report this
as an omitted-dependence limitation and will not claim that the count-plus-mark
model reproduces within-window path clustering unless the available scene-held
out evidence supports it.

### Nested scene validation and family selection

Use outer LOSO over all 13 `scene_id` values. Within each outer training set,
select each marginal family by inner LOSO over the remaining 12 whole scenes,
using scene-macro held-out log score with the same weights for all candidates.
No test-scene statistic may affect family selection, parameter fitting,
copula fitting, scaling, or missingness decisions. Report every outer fold,
support count, failed fit, selected family, marginal score, copula increment,
and count score. Fold summaries are descriptive because the outer training
sets overlap; use scenes, not paths, as the reporting unit and do not call
fold-resampled intervals independent-experiment confidence intervals.

### CIR/PDP relationship analysis

Keep the Gate-F table as the window-level response source. From the Stage2 MPC
marks, derive per selected window (including `N=0`) the relative-power-weighted
excess-delay centroid and RMS spread, treating the direct reference as unit
relative power at zero excess delay. Compare an intercept-only scene-trained
mean against one-predictor linear scene-out models:

- weighted SAGE delay spread -> `pdp_rms_width_code_delay_samples`;
- weighted SAGE delay centroid ->
  `pdp_peak_minus_sage_direct_delay_samples`.

Fit transformations and coefficients on outer training scenes only. Report
per-scene MAE/RMSE and scene-macro deltas, with the 63 retained boundary-peak
windows explicitly flagged and included. These are empirical cross-measurement
associations/predictions sharing source data, not independent physical
validation or a SAGE-alpha reconstruction of CIR. Do not use alpha phase as a
continuous temporal predictor.

## Implementation and outputs

- Reuse the existing Stage2 schemas and model-family definitions; add one
  focused WP6 analysis module/runner and tests rather than a new framework.
- Create one new timestamped WP6 result directory; refuse overwrite.
- Include input manifest and SHA-256, nested-fold manifests, selected families
  and parameters, count probabilities, dependence matrices, per-window and
  per-scene score tables, CIR/PDP LOSO predictions, summary JSON, figures,
  execution/test logs, report, and an independent validator/review record.
- Use a deterministic seed only for visual/model simulation examples; primary
  fit and scores are deterministic. Any uncertainty interval must resample
  scenes and be labelled descriptive; do not bootstrap individual MPC rows.
- Keep bulky/full derived outputs in the project results namespace; Git stages
  only the appropriate code, reports, compact summaries and figures, not the
  already frozen source payloads.

## Acceptance boundary

Report empirical/count-model performance, independent-vs-copula held-out
scene score differences, selected marginal families and parameter stability,
tail calibration/support, per-scene failures, and the CIR/PDP held-out
association comparison. State whether the copula improves the scene-macro
held-out composite mark score and whether either PDP target improves over the
intercept baseline; do not require a complex model to win. A valid negative
result supports retaining the simpler baseline. Recommend Gate G only after
independent review of the actual outputs; code execution alone is not Gate G.
