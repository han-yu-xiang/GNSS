# Environment × Elevation Stage3 Academic Path Model V1

状态：**Built / independent QA pending in separate auditor**。这是基于 Stage3 reliable/persistent multipath estimates 的 measurement-derived conditional model，不是物理传播真值模型。

## Scope and frozen population

输入为已通过 QA 的 `dataset_generation_logs\channel_modeling\stage3_statistical_unit_track_reassessment_20260829_r1`：783 条 academic Stage3 path observations、445 centers、50 runs、12 scenes、18 PRNs；716 条 observation 具有连续仰角。保守 reciprocal Stage3 association 提供 366 个 algorithm-level tracks，所有 observation 保留，权重为 `1/track_size`。Stage4 strict-confirmed subset 只用于敏感性验证。

Source snapshot unchanged: **YES**; prior Stage3 unit namespace unchanged: **YES**; frozen production hashes match: **YES**.

## Primary weighted population and cell support

Primary formal unit is `WEIGHTED_OBSERVATION`; inference must be scene/run clustered and use scene-block bootstrap. The model stores raw row count, sum of weights, Kish effective sample size, track/run/scene/PRN counts for every cell. `Highway/Open–LOW` remains `NO_DIRECT_SUPPORT` and receives no synthetic empirical observations.

| Cell support status | Cell count |
|---|---:|
| `DATA_SUPPORTED` | 5 |
| `SPARSE_PARTIAL_POOLING` | 4 |
| `PRIOR_DOMINANT` | 2 |
| `NO_DIRECT_SUPPORT` | 1 |

The machine-readable `cell_support_matrix.csv` has all 12 cells and keeps continuous `elevation_deg` in the source population table. Support labels use scene count, run count, and Kish effective support in addition to row count.

## Marginal family selection and hierarchy

Formal global grouped leave-one-scene-out selections for the weighted primary are: `{"doppler_offset_hz": "normal", "excess_delay_samples": "lognormal", "relative_power_db": "normal"}`. Candidate scores report weighted in-sample likelihood, grouped held-out likelihood, AIC/AICc/BIC, fold scenes, and validity separately; no row-random split was used. The formal hierarchy is global → environment → environment×elevation, with fixed parent pseudo-quantile weight documented in `model_config.json`; no Stage4 family was copied into the Stage3 selection.

Cells with direct evidence use local weighted observations plus the pre-specified environment parent; cells without direct evidence use the environment parent only and remain explicitly non-empirical for that cell.

## Joint dependence

The primary joint layer uses weighted midranks followed by a Gaussian copula. Global and supported environment/cell levels are stored explicitly. Sparse or empty cells use an environment-parent copula or are marked `NO_DIRECT_SUPPORT`; a cell-specific dependence estimate is not silently invented.

## Uncertainty and observation-dependence sensitivity

Scene-block bootstrap uses seed `2026082901` and 1000 replicates; run-block sensitivity uses seed `2026082902` and the same replicate count. The comparison tables retain raw observation/clustered, weighted observation, and algorithm-track-median views. The previous sensitivity magnitudes are not used as tuning targets.

## Stage4 sensitivity

Stage4 strict-confirmed paths are compared only as a high-confidence validation baseline. Comparable Stage3/Stage4 summary rows: 45/45; CDF grids, medians, IQR, selected quantiles, selected families, and bootstrap intervals are in `stage3_stage4_sensitivity.csv` and `stage3_stage4_cdf_comparison.csv`. Agreement is not required; sparse or missing cells are labeled `INCONCLUSIVE`.

## Continuous elevation exploration

The continuous-elevation analysis is exploratory and does not replace LOW/MID/HIGH. It reports weighted rank correlation, linear diagnostics, and scene-block slope intervals. `CONTINUOUS_ELEVATION_V2=NOT_SUPPORTED`; the full per-environment evidence is in `continuous_elevation_diagnostics.csv`.

## Derived channel statistics and persistence

Stage3 center diagnostics include power-weighted mean excess delay, conditional RMS delay spread, Doppler centroid, conditional RMS Doppler spread, algorithm-observed component count, aggregate/strongest relative multipath power, and algorithm-track persistence duration. These are not total-channel or physical-reflector quantities. `IS_RICEAN_K_SCIENTIFICALLY_IDENTIFIABLE=NO`: Stage3 lacks a defensible physical main/reference component power and phase definition, so no K-factor is computed.

## Commander decision block

```text
ACADEMIC_MODELING_POPULATION_V2 = APPLIED
PRIMARY_STATISTICAL_UNIT = WEIGHTED_OBSERVATION
ENV_ELEV_STAGE3_MODEL_V1 = PASS_WITH_LIMITATIONS
CURRENT_10MHZ_STAGE3_MODEL = ADEQUATE_WITH_LIMITATIONS
STAGE4_SENSITIVITY_RESULT = PARTIALLY_CONSISTENT
CONTINUOUS_ELEVATION_V2 = NOT_SUPPORTED
PROCESS_20_46_MHZ_NEXT = CONDITIONAL
NEW_DATA_COLLECTION_REQUIRED = CONDITIONAL
```

Interpretation: the current 10 MHz Stage3 population is adequate for a bounded descriptive Environment×Elevation path-parameter model, but not for an unrestricted physical channel claim. Additional data are conditionally useful for Highway/Open–LOW, independent-scene replication, sparse cells, and continuous-elevation generalization; no collection or 20.46 MHz processing is started by this task.

## Execution and artifact boundary

New-only model namespace: `E:\GNSS_Multipath_Project\dataset_generation_logs\channel_modeling\environment_elevation_stage3_path_model_v1_20260829_r2`. Report: `E:\GNSS_Multipath_Project\docs\ENVIRONMENT_ELEVATION_STAGE3_ACADEMIC_MODEL_V1_R2_REPORT.md`. Existing Stage0–Stage4 source artifacts, Stage4 model, database, prior Stage3 reassessment, Engineering/Paper handoffs, and production hashes were not modified. Raw IQ read: `NO`; MATLAB: `NO`; SAGE: `NO`; batch: `NO`; final model fit in the sense of a deployable darkroom generator: `NO`.

Build output tables include `source_population_audit.csv`, `cell_support_matrix.csv`, `weighted_parameter_summary.csv`, `candidate_family_scores.csv`, `selected_marginal_models.csv`, `global_models.csv`, `environment_models.csv`, `environment_elevation_models.csv`, `joint_dependence_models.csv`, `scene_block_bootstrap.csv`, `run_block_sensitivity.csv`, `observation_track_sensitivity.csv`, `stage3_stage4_sensitivity.csv`, `stage3_stage4_cdf_comparison.csv`, `continuous_elevation_diagnostics.csv`, `derived_channel_statistics.csv`, `persistence_duration_statistics.csv`, model diagnostics, sampling contract, receipt, and manifest.

NEXT_DECISION_REQUIRED=AUTHOR/COMMANDER REVIEW OF MODEL LIMITATIONS AND WHETHER TO AUTHORIZE A SEPARATE 20.46 MHz DESIGN; no automatic continuation.
