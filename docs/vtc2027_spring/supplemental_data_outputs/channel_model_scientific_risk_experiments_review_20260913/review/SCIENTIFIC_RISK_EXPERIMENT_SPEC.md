# Scientific-risk supplemental experiment specification

Date: 2026-09-13

## Objective

Test whether the two-component Doppler and relative-power mixtures and the fixed two-slope power-delay model remain defensible when complete measurement scenes, rather than individual time rows, are held out.

## Immutable input population

- Source: `urban_mountain_stage3_elevation_model_review_v3_conditional_gmm/population/gmm_feature_population.csv`
- Inclusion rule: `primary_population_included == true`
- Expected denominator: 518 time-indexed persistent component estimates
- Expected groups: Urban 346; Mountain/Valley 172
- Expected satellite tracks: 236
- Expected scenes: Urban 6; Mountain/Valley 3
- Weight rule: recompute `1 / number of retained rows in the track` within every resampled data set, so each track has total weight one.
- No row may be removed as an outlier.
- Elevation is outside this experiment.

## Experiment A: mixture complexity

For signed relative Doppler and relative power, fit one-, two-, and three-component one-dimensional Gaussian mixture models separately in Urban and Mountain/Valley. Use deterministic weighted EM with ordered means, a standard-deviation floor, at least five units of effective weight per component, and several deterministic starts. Report full-data log likelihood, AIC, BIC, maximum weighted CDF deviation, and leave-one-scene-out negative log predictive density (NLPD).

The primary complexity decision uses the one-standard-error rule: find the model with the lowest mean scene-held-out NLPD, then choose the smallest component count whose mean is no larger than the best mean plus the best model's standard error. AIC, BIC, and CDF deviation are secondary diagnostics.

## Experiment B: power-delay breakpoint

Compare three environment-specific weighted regressions:

1. one straight line;
2. two connected lines with the current fixed breakpoint at 1.95 samples;
3. two connected lines whose breakpoint is chosen from 1.25 to 3.25 samples in 0.10-sample steps using training scenes only.

For every outer leave-one-scene-out fold, fit only on the remaining scenes and evaluate weighted RMSE and MAE on the untouched scene. The selected-breakpoint model must never use the held-out scene when choosing its breakpoint. Report fold-level errors, mean errors, full-data breakpoints, and the set of breakpoints selected across folds.

## Experiment C: scene-block stability

Use 1000 deterministic scene-block bootstrap replicates per environment. Refit the paper's two-component Doppler and power mixtures and the fixed-breakpoint two-line model. Sort mixture components by mean before collecting percentiles. Report 2.5%, median, and 97.5% intervals. Replicated scenes receive unique replicate identifiers before track weights are recomputed.

## Scientific gate

- Outputs remain review-only in this directory.
- No manuscript, formal figure, table, handoff, source population, SAGE output, raw IQ, or MATLAB file is modified.
- No result is inserted into the paper automatically.
- A result is paper-eligible only after independent QA confirms denominators, track weights, complete scene folds, finite fits, component ordering, bootstrap completeness, and source-file integrity.
- A failed or mixed robustness result is reported as such and is not rewritten as support.

