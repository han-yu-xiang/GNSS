# Mainline Stage2 Gate G Supplement — Design

## Purpose and boundary

Resolve only the two unresolved WP6 Gate G questions: (1) whether Stage2-selected
MPC mark marginals are stable conditional on selected-window MPC count and path
rank, and (2) whether a Gaussian copula improves held-out-scene prediction when
the SAGE delay grid is scored as discrete data. This is a new, bounded analysis
of the frozen light CSVs. It does not rerun SAGE/CIR/alpha production, alter any
prior result package, or claim an unconditional multipath process, calibrated
physical channel, or coherent temporal channel.

## Frozen input and observed mechanism

Use the WP4 final linkage CSV already pinned by WP6, SHA-256
`8db941db20e684108d13583d67ee20cde543bf2a36ca01013d1288b48231c80b`, and the
matching selected-window feature table pinned in WP6. Retain all 7,847 selected
windows and 8,914 MPC rows; count-conditioned mark analysis uses only the
4,273 windows with at least one Stage2 MPC and remains conditional on Stage2
selection. No Stage0-unselected window is assigned zero MPC.

The SAGE implementation uses `delayStepSamples=0.1`, `samplesPerChip=10`, and
`minimumPathSeparationSamples=1.0`; therefore excess delay is an algorithmic
lattice output at 0.01 chip and the selected MPC support begins at 0.10 chip.
Treat it as a discrete grid, not as a continuous exact observation. The source
sorts every model's paths by delay before `flattenStage2` assigns sequential
`path_id`; path IDs are ordered component ranks, not exchangeable physical
labels.

## Models and validation

1. **M0:** count-invariant scene-balanced product marginals for delay,
   signed Doppler, and relative power.
2. **M1:** marginals selected and fitted separately for `N_MPC=1,2,3`, with
   complete-scene outer LOSO and training-only inner scene-LOSO family choice.
   Compare both models on identical held-out MPC rows; score per path and
   aggregate first within window, then equally across scenes. Keep the per-N
   support and per-scene results. This is a conditional marginal prediction
   comparison, not a path-set joint likelihood.
3. **C0/C1:** Gaussian-copula alternatives paired with M0/M1 marginals,
   estimated only on each outer training set. For each observed delay lattice
   value `d`, use its Voronoi cell `[max(0.10,d-0.005), d+0.005)` under the
   fitted continuous latent delay CDF, normalized conditional on delay at
   least 0.10 chip. Score the delay by the cell probability; score Doppler and
   power by their continuous densities. Integrate the Gaussian-copula density
   over the delay cell conditional on the two continuous PITs. The independence
   limit must exactly recover the product of discrete delay mass and the two
   continuous densities. This is a scene/window-balanced composite score for
   one selected MPC mark, not a likelihood for an ordered window path set.

Outer held-out scenes are all 13 complete scenes. The same held-out rows,
scene/window weighting, and nested family-selection rule are used for paired
models. No path-row confidence intervals, p-values, or independence claims;
report scene-level score differences and their range/sign counts as descriptive
generalization evidence. Preserve all fit failures and low-support strata.

Separately report per-scene support and within-window rank contrasts by count.
The deterministic delay ordering and any reproducible rank patterns must be
treated as SAGE selection/order structure. Do not infer physical cause from
these observational conditional differences.

## Gate G interpretation boundary

Report separately: validated Stage2-selected count/marginal prediction;
scene-out-supported within-mark dependence (if any); any count/rank-conditioned
empirical structure; assumptions still required to generate a whole ordered
window path set; and unvalidated time-varying complex physical-channel
capability. A score gain is not sufficient to validate the whole-window
generator. If the complete ordered-set dependence is not validated, Gate G
must remain pending or be explicitly limited to the narrower verified model
scope; do not rename the model to imply a stronger result.

## Deliverables and safety

Write new source, tests, compact tables, figures, logs, provenance and a Chinese
review report under a new `wp6_gateg_*` result directory. Never overwrite the
prior WP6 packages or frozen CSVs. Update the master plan and engineering/paper
handoffs with the actual evidence and one next priority. Commit only the new
Gate G supplement, relevant tests/code, report/compact outputs and those three
documents; preserve unrelated untracked files. Push normally to the existing
research branch and update Draft PR #2 without merging.
