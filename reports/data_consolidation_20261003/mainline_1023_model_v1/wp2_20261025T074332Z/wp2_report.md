# WP2 Stage2 robustness closure

Status: `COMPLETED_WITH_LIMITATIONS` (bounded exploratory robustness evidence; not formal Gate G).

## Frozen population and method

- 8,914 Stage2 MPC path records, 7,847 Stage2-selected windows, 83 runs, 13 scenes.
- Window count histogram on the selected-window denominator: {"0": 3574, "1": 1412, "2": 1081, "3": 1780}.
- The 7,847 windows were selected from the 285,752 Stage0-valid windows. All count estimands are conditional on that Stage2 selection and capped observed support 0–3; unselected Stage0 windows were not assigned zero MPC.
- Reused frozen V0 scene-LOSO fold parameters/ranks; did not rerun V0 fits. Tail quantiles use each fold's training-only parameters. Power-delay and count models use full-scene LOSO with equal total weight per training scene and whole-scene bootstrap; no row-level p-values are emitted.
- Runtime: 2.7 s. No raw IQ, MAT/HDF5/CIR payload, MATLAB, SAGE, GNSS-SDR, or Task 5 production was accessed or invoked.

## Scene sensitivity and fit ranking

- ENV:Urban / doppler_offset_hz / laplace: rank-1 1/6 valid scene folds; rank-1 held-out scenes=["F1023_V70_D0120_P5"]; support-limited 0, failed 0.
- ENV:Urban / doppler_offset_hz / normal: rank-1 4/6 valid scene folds; rank-1 held-out scenes=["F1023_V70_D0120_P7", "F1023_V70_D0120_P8", "F1023_V70_D0122_P1", "F1023_v50_D0127_P1"]; support-limited 0, failed 0.
- ENV:Urban / doppler_offset_hz / student_t: rank-1 1/6 valid scene folds; rank-1 held-out scenes=["F1023_V70_D0120_P1"]; support-limited 0, failed 0.
- ENV:Urban / excess_delay_chips / gamma: rank-1 0/6 valid scene folds; rank-1 held-out scenes=[]; support-limited 0, failed 0.
- ENV:Urban / excess_delay_chips / lognormal: rank-1 6/6 valid scene folds; rank-1 held-out scenes=["F1023_V70_D0120_P1", "F1023_V70_D0120_P5", "F1023_V70_D0120_P7", "F1023_V70_D0120_P8", "F1023_V70_D0122_P1", "F1023_v50_D0127_P1"]; support-limited 0, failed 0.
- ENV:Urban / excess_delay_chips / weibull: rank-1 0/6 valid scene folds; rank-1 held-out scenes=[]; support-limited 0, failed 0.
- ENV:Urban / relative_power_db / laplace: rank-1 1/6 valid scene folds; rank-1 held-out scenes=["F1023_V70_D0120_P5"]; support-limited 0, failed 0.
- ENV:Urban / relative_power_db / normal: rank-1 4/6 valid scene folds; rank-1 held-out scenes=["F1023_V70_D0120_P1", "F1023_V70_D0120_P7", "F1023_V70_D0120_P8", "F1023_v50_D0127_P1"]; support-limited 0, failed 0.
- ENV:Urban / relative_power_db / student_t: rank-1 1/6 valid scene folds; rank-1 held-out scenes=["F1023_V70_D0122_P1"]; support-limited 0, failed 0.
- GLOBAL / doppler_offset_hz / laplace: rank-1 2/13 valid scene folds; rank-1 held-out scenes=["F1023_V120_D0121_P2", "F1023_V70_D0117_P2"]; support-limited 0, failed 0.
- GLOBAL / doppler_offset_hz / normal: rank-1 6/13 valid scene folds; rank-1 held-out scenes=["F1023_V70_D0117_P4", "F1023_V70_D0120_P8", "F1023_V70_D0122_P1", "F1023_V70_D0122_P2", "F1023_V80_D0117_P8", "F1023_v90_D0117_P7"]; support-limited 0, failed 0.
- GLOBAL / doppler_offset_hz / student_t: rank-1 5/13 valid scene folds; rank-1 held-out scenes=["F1023_V70_D0120_P1", "F1023_V70_D0120_P5", "F1023_V70_D0120_P7", "F1023_V70_D0120_P9", "F1023_v50_D0127_P1"]; support-limited 0, failed 0.
- GLOBAL / excess_delay_chips / gamma: rank-1 0/13 valid scene folds; rank-1 held-out scenes=[]; support-limited 0, failed 0.
- GLOBAL / excess_delay_chips / lognormal: rank-1 13/13 valid scene folds; rank-1 held-out scenes=["F1023_V120_D0121_P2", "F1023_V70_D0117_P2", "F1023_V70_D0117_P4", "F1023_V70_D0120_P1", "F1023_V70_D0120_P5", "F1023_V70_D0120_P7", "F1023_V70_D0120_P8", "F1023_V70_D0120_P9", "F1023_V70_D0122_P1", "F1023_V70_D0122_P2", "F1023_V80_D0117_P8", "F1023_v50_D0127_P1", "F1023_v90_D0117_P7"]; support-limited 0, failed 0.
- GLOBAL / excess_delay_chips / weibull: rank-1 0/13 valid scene folds; rank-1 held-out scenes=[]; support-limited 0, failed 0.
- GLOBAL / relative_power_db / laplace: rank-1 2/13 valid scene folds; rank-1 held-out scenes=["F1023_V70_D0117_P2", "F1023_V70_D0120_P5"]; support-limited 0, failed 0.
- GLOBAL / relative_power_db / normal: rank-1 3/13 valid scene folds; rank-1 held-out scenes=["F1023_V120_D0121_P2", "F1023_V70_D0120_P7", "F1023_v50_D0127_P1"]; support-limited 0, failed 0.
- GLOBAL / relative_power_db / student_t: rank-1 8/13 valid scene folds; rank-1 held-out scenes=["F1023_V70_D0117_P4", "F1023_V70_D0120_P1", "F1023_V70_D0120_P8", "F1023_V70_D0120_P9", "F1023_V70_D0122_P1", "F1023_V70_D0122_P2", "F1023_V80_D0117_P8", "F1023_v90_D0117_P7"]; support-limited 0, failed 0.

Per-fold parameter estimates and interquartile ranges are descriptive sensitivity summaries across overlapping LOSO training sets, not independent estimates or confidence intervals. Failed fits and support-limited folds remain visible.

## Held-out tails

Evaluated p01/p05/p10/p90/p95/p99 held-out quantile calibration using saved training-fold parameters. 324 family/scene/quantile records are flagged below the predeclared expected-tail support of 10 observations. Tail evidence is therefore limited where flagged; it is not converted into a pass claim.

## Power-delay relationship and scene-out prediction

- GLOBAL: negative fitted slope in 13/13 held-out fits; slope median/range -2.50632 [-10.5248, -2.25958] dB/chip; conditional-minus-marginal scene-macro log score -0.0605013 (whole-scene bootstrap 95% interval [-0.210037, 0.0174261]); RMSE delta 0.182619 dB.

Fitted slopes are predictive associations in the Stage2-selected MPC population, not causal effects or a universal law. A positive macro score delta favors the conditional candidate on average; the 13-scene unit, its interval, RMSE and fold-direction consistency must all be considered together.

## Stage2-selected-window MPC-count candidates

- EMPIRICAL_CATEGORICAL: evaluated 13/13 scenes; macro log-score delta vs empirical categorical = 0 over 13 finite paired scenes (whole-scene 95% interval [0, 0]); macro RMSE delta = 0.0; unseen-category scenes=0, boundary fits=0.
- TRUNCATED_POISSON: evaluated 13/13 scenes; macro log-score delta vs empirical categorical = -0.171584 over 13 finite paired scenes (whole-scene 95% interval [-0.250062, -0.0881262]); macro RMSE delta = 1.708035422500241e-17; unseen-category scenes=0, boundary fits=0.
- TRUNCATED_NB2: evaluated 13/13 scenes; macro log-score delta vs empirical categorical = -0.0182553 over 13 finite paired scenes (whole-scene 95% interval [-0.0491595, 0.0139787]); macro RMSE delta = -0.000616141422200507; unseen-category scenes=0, boundary fits=13.

The empirical categorical candidate has no smoothing; unseen held-out categories receive zero probability and are explicitly reported. Parametric PMFs are normalized on 0–3. Count-model conclusions apply only to Stage2-selected windows; these results do not describe all Stage0 windows or justify imputing unselected windows as zero.

Boundary/failure accounting: - TRUNCATED_NB2: {"BOUNDARY_MEAN_AT_INFINITY": 13} A boundary candidate is not interpreted as a finite interior MLE; its boundary status and any limiting PMF are retained explicitly.

## Task 5 and alpha boundary

Not sampled in this invocation.

The real alpha export pilot remains deferred until WP2 review. This report does not establish Gate E/F, complete CIR association, or formal model acceptance.

## Files

See the adjacent `*_by_fold.csv` / `*_by_scene.csv`, summary CSVs, and `wp2_manifest.json` for fold-level aggregates, code/input/output hashes, and explicit support statuses. Outputs contain no `(run_id, window_id, path_id)` keys or exact coordinates.
