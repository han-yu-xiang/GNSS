# Environment--Elevation Partially Pooled 3D GMM Design

## Objective

Build one conditional three-dimensional statistical model for excess delay, absolute relative Doppler magnitude, and relative power. The paper-facing results are conditioned on Urban or Mountain/Valley and LOW/MID/HIGH elevation. A pooled model is used only as a parent for regularization and fallback, not as the scientific headline result.

## Frozen input and semantic boundary

- Source population: `docs/vtc2027_spring/supplemental_data_outputs/urban_mountain_stage3_elevation_model_review_v2_doppler_audit/population/population_primary_admitted.csv`.
- Population: 518 persistent path observations, 236 algorithm-level tracks, 36 runs, 9 scenes, and 18 PRNs.
- Elevation-ready subset: 487 observations. The 31 missing-elevation observations remain available to the environment parent but are never assigned to LOW/MID/HIGH.
- Environments: Urban and Mountain/Valley only.
- Elevation groups: LOW=`[0,30)`, MID=`[30,60)`, HIGH=`[60,90]` degrees.
- Weight: `track_weight_recomputed_primary`; each algorithm-level track sums to one.
- Stage4 is not used. The rows remain persistent path observations, not confirmed physical paths.
- Raw IQ, MATLAB, SAGE, and batch execution are outside scope.

## Model variables

For observation `i`, define the transformed vector

```text
x_delay_i   = log(excess_delay_samples_i)
x_doppler_i = log1p(abs(doppler_offset_hz_i) / 1 Hz)
x_power_i   = relative_power_db_i
z_i         = training-fold weighted standardization of
              [x_delay_i, x_doppler_i, x_power_i]
```

The signed Doppler field is preserved in the feature table. The absolute value is the primary model variable because the model targets path-separation magnitude. This does not assert physical sign symmetry. A signed-Doppler sensitivity model is required before paper admission.

## Conditional partially pooled GMM

For environment `e`, elevation band `b`, and component `k`:

```text
p(z | e, b) = sum_k pi[e,b,k] * Normal(z | mu[e,k], Sigma[k])
```

The model uses:

- global parent weights `pi_global[k]` and means `mu_global[k]`;
- environment weights `pi_env[e,k]` shrunk toward `pi_global[k]`;
- environment means `mu_env[e,k]` shrunk toward `mu_global[k]`;
- cell weights `pi_cell[e,b,k]` shrunk toward `pi_env[e,k]`;
- component covariance matrices `Sigma[k]` shared across environments and elevation bands.

The pooled parent controls sparse cells but is not reported as an all-path propagation law. Missing-elevation observations use `pi_env[e,k]` during training and never contribute to `pi_cell[e,b,k]`.

One track-equivalent pooling strength `kappa` is used for environment weights, environment means, and cell weights. Candidate values are `{4, 8, 16, 32}`. Component counts are `K={1,2,3}`. The component labels are ordered by ascending relative-power mean, then absolute-Doppler mean, then delay mean to prevent label switching across folds.

## Fitting and numerical policy

- Custom weighted EM is used so fractional track weights are honored exactly.
- Maximum iterations: 500.
- Relative log-likelihood tolerance: `1e-7`.
- Covariance eigenvalue floor in standardized space: `1e-5`.
- Mixture-weight floor: `1e-6`, followed by normalization.
- Deterministic restarts: 10 per `(K,kappa,fold)` candidate.
- A candidate is invalid if any fold is non-finite, fails monotonic log-likelihood beyond `1e-8`, produces a covariance eigenvalue below the floor, or leaves a global component with weighted responsibility below four track-equivalent observations.

## Validation and selection

- Grouping unit: held-out scene; all rows from one scene are excluded together.
- Primary metric: weighted held-out negative log predictive density in the original transformed three-dimensional variable.
- Common comparison metric: deterministic three-dimensional energy score using 4096 conditional draws per held-out cell.
- Candidate grid: 12 combinations from `K={1,2,3}` and `kappa={4,8,16,32}`.
- Selection: choose the lowest scene-grouped loss among valid candidates. Prefer the smaller `K` when the paired scene-block 95% interval for the more complex candidate versus the smaller model includes zero.
- Stability: 1000 scene-block bootstrap replicates with a frozen seed.
- Baselines: `K=1` conditional Gaussian and the existing v2 marginal-plus-copula model transformed to absolute Doppler.
- Signed-Doppler sensitivity: fit the selected architecture with signed Doppler. If it improves the paired scene-block energy score with a 95% interval entirely below zero, stop before discarding sign and return to the author.

## Cell support and pooling interpretation

| Cell | Observations | Tracks | Scenes | Model treatment |
|---|---:|---:|---:|---|
| Urban--LOW | 18 | 8 | 3 | strongly pooled |
| Urban--MID | 169 | 74 | 5 | data-supported |
| Urban--HIGH | 129 | 64 | 5 | data-supported |
| Mountain/Valley--LOW | 22 | 12 | 3 | strongly pooled |
| Mountain/Valley--MID | 117 | 53 | 3 | data-supported with scene limitation |
| Mountain/Valley--HIGH | 32 | 15 | 2 | strongly pooled |

No cell receives an independent covariance matrix. Mixture components are statistical components and must not be labelled as reflector types or physical propagation mechanisms.

## Review visualizations

1. A 2-by-3 environment--elevation panel. Each panel shows the modeled delay--power density contours, empirical observations, and absolute-Doppler magnitude by a common color scale.
2. One corner-plot page per cell showing all three pairwise projections and one-dimensional marginals. This is an internal diagnostic, not automatically a VTC figure.
3. A 2-by-3 mixture-weight heatmap with observation, track, and scene counts printed in each cell.
4. A compact cell summary table reporting support, selected weights, transformed-back medians, 90% intervals, and model status.

No empirical CDF figure is produced because the author previously declined a CDF figure.

## Admission gate

The model remains review-only until independent QA verifies source hashes, population counts, weights, scene-fold isolation, deterministic reproduction, finite likelihoods, positive-definite covariance matrices, component support, bootstrap completeness, and figure/table consistency. The author must approve the selected `K`, `kappa`, signed-versus-absolute Doppler decision, and candidate visualizations before any isolated manuscript copy is edited.

