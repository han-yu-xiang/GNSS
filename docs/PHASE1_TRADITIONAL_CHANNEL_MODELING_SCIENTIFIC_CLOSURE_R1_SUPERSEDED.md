# Phase‑1 Traditional Channel Modeling Scientific Closure

状态：**Scientific closure built from the canonical r3 model; independent QA is recorded in the same new-only namespace.**

## 1. Scope, canonical input, and scientific unit

This closure reads only `dataset_generation_logs\channel_modeling\environment_elevation_stage3_path_model_v1_20260829_r3` and preserves r3 as the canonical traditional model. The primary population is 783 academic Stage3 reliable/persistent path observations, represented as `WEIGHTED_OBSERVATION` with weight `1 / algorithm_track_size`; dependence is handled through scene/run clustering and scene-block bootstrap. The population contains 445 centers, 366 algorithm-level tracks, 716 elevation-ready observations, 50 runs, 12 scenes, and 18 PRNs.

Stage3 observations and algorithm tracks are measurement/algorithm units, not physical reflector identities. Persistence is algorithm-observed persistence only. Stage4 strict-confirmed paths are a high-confidence validation subset and are not external truth or a Stage3 selection input.

## 2. What propagation/channel trends are supported

The formal path-level quantities are excess delay, signed relative Doppler, and relative power in dB. The weighted global candidate families selected by grouped leave-one-scene-out evidence are delay=Lognormal, signed Doppler=Normal, and relative power=Normal. Environment, elevation, and interaction claims below are bounded by support labels and scene/run dependence treatment.

| Parameter | Environment effect | Elevation effect | Environment×elevation interaction |
|---|---|---|---|
| `excess_delay_samples` | `INCONCLUSIVE` | `INCONCLUSIVE` | `PARTIAL` |
| `doppler_offset_hz` | `INCONCLUSIVE` | `INCONCLUSIVE` | `INCONCLUSIVE` |
| `relative_power_db` | `INCONCLUSIVE` | `INCONCLUSIVE` | `PARTIAL` |

Machine-readable details are in `effect_table.csv`, `elevation_characterization.csv`, and `environment_elevation_interaction.csv`.

## 3. Environment characterization

The following summaries describe supported measurement-derived behavior; they do not force every environment to have a unique physical signature.

| Environment | Support | Delay | Doppler | Power | Joint dependence | Limitations |
|---|---|---|---|---|---|---|
| Urban | DATA_SUPPORTED | NO_ROBUST_DIFFERENCE (lognormal) | NO_ROBUST_DIFFERENCE (normal) | NO_ROBUST_DIFFERENCE (normal) | {"delay_doppler": -0.002766412808121039, "delay_power": -0.5591711321789862, "doppler_power": 0.02416025924154888} | No direct elevation support in Highway/Open–LOW; Special Reflective and Mountain/Valley contain sparse/partial cells; Stage4 is selection-sensitive. |
| Special Reflective | SPARSE_PARTIAL_POOLING | INCONCLUSIVE (lognormal) | INCONCLUSIVE (normal) | INCONCLUSIVE (normal) | {"delay_doppler": -0.0036391229012471735, "delay_power": -0.562377520482554, "doppler_power": 0.03823237249460862} | No direct elevation support in Highway/Open–LOW; Special Reflective and Mountain/Valley contain sparse/partial cells; Stage4 is selection-sensitive. |
| Mountain/Valley | DATA_SUPPORTED | NO_ROBUST_DIFFERENCE (lognormal) | NO_ROBUST_DIFFERENCE (normal) | NO_ROBUST_DIFFERENCE (normal) | {"delay_doppler": 0.04079179231795875, "delay_power": -0.6368049356263455, "doppler_power": 0.01301619939647532} | No direct elevation support in Highway/Open–LOW; Special Reflective and Mountain/Valley contain sparse/partial cells; Stage4 is selection-sensitive. |
| Highway/Open | PRIOR_DOMINANT | INCONCLUSIVE (lognormal) | INCONCLUSIVE (normal) | INCONCLUSIVE (normal) | {"delay_doppler": -0.0036391229012471735, "delay_power": -0.562377520482554, "doppler_power": 0.03823237249460862} | No direct elevation support in Highway/Open–LOW; Special Reflective and Mountain/Valley contain sparse/partial cells; Stage4 is selection-sensitive. |

If an effect table row is `NO_ROBUST_DIFFERENCE`, that environment/parameter comparison is reported as `NO_ROBUST_DIFFERENCE`, not as a forced separation.

## 4. Elevation characterization

LOW/MID/HIGH remains the formal Phase‑1 interface. Continuous elevation is exploratory and does not replace these bands.

| Band | Parameter | n | Effective n | Effect vs elevation-ready global | Evidence |
|---|---|---:|---:|---:|---|
| LOW | excess_delay_samples | 121 | 93.5085008 | -0.1 | INCONCLUSIVE |
| MID | excess_delay_samples | 341 | 252.673094 | -0.1 | INCONCLUSIVE |
| HIGH | excess_delay_samples | 254 | 197.595349 |  | INCONCLUSIVE |
| LOW | doppler_offset_hz | 121 | 93.5085008 | 20.2762192 | INCONCLUSIVE |
| MID | doppler_offset_hz | 341 | 252.673094 | -0.630302182 | INCONCLUSIVE |
| HIGH | doppler_offset_hz | 254 | 197.595349 | -4.75110306 | INCONCLUSIVE |
| LOW | relative_power_db | 121 | 93.5085008 | 5.47972973 | INCONCLUSIVE |
| MID | relative_power_db | 341 | 252.673094 | -0.594284981 | INCONCLUSIVE |
| HIGH | relative_power_db | 254 | 197.595349 | -1.89700766 | INCONCLUSIVE |

The empty `Highway/Open–LOW` cell is not used to infer a low-elevation Highway/Open effect.

## 5. Environment × elevation interaction

Interaction is assessed through within-environment band contrasts and support/LOSO evidence; visual cell differences alone are not treated as interactions.

| Environment | Parameter | Direct band pair | Interaction label | Support |
|---|---|---|---|---|
| Urban | excess_delay_samples | LOW→HIGH | INCONCLUSIVE | DATA_SUPPORTED |
| Special Reflective | excess_delay_samples | LOW→HIGH | INCONCLUSIVE | SPARSE_PARTIAL_POOLING |
| Mountain/Valley | excess_delay_samples | LOW→HIGH | PARTIAL | SPARSE_PARTIAL_POOLING |
| Highway/Open | excess_delay_samples | MID→HIGH | INCONCLUSIVE | PRIOR_DOMINANT |
| Urban | doppler_offset_hz | LOW→HIGH | INCONCLUSIVE | DATA_SUPPORTED |
| Special Reflective | doppler_offset_hz | LOW→HIGH | INCONCLUSIVE | SPARSE_PARTIAL_POOLING |
| Mountain/Valley | doppler_offset_hz | LOW→HIGH | INCONCLUSIVE | SPARSE_PARTIAL_POOLING |
| Highway/Open | doppler_offset_hz | MID→HIGH | INCONCLUSIVE | PRIOR_DOMINANT |
| Urban | relative_power_db | LOW→HIGH | INCONCLUSIVE | DATA_SUPPORTED |
| Special Reflective | relative_power_db | LOW→HIGH | PARTIAL | SPARSE_PARTIAL_POOLING |
| Mountain/Valley | relative_power_db | LOW→HIGH | INCONCLUSIVE | SPARSE_PARTIAL_POOLING |
| Highway/Open | relative_power_db | MID→HIGH | INCONCLUSIVE | PRIOR_DOMINANT |

Aggregated interaction labels:

- `excess_delay_samples`: `PARTIAL`
- `doppler_offset_hz`: `INCONCLUSIVE`
- `relative_power_db`: `PARTIAL`

## 6. Channel-level statistics

Path-level fitted parameters are kept separate from center/channel-level diagnostics. The available derived quantities are power-weighted mean excess delay, conditional RMS delay spread, Doppler centroid, conditional RMS Doppler spread, algorithm-observed reliable component count, aggregate/strongest relative multipath power, and algorithm-observed persistence.

The conditional RMS quantities require multiple Stage3 observations within a center; relative-power quantities are not absolute RF power. No Ricean K-factor is computed: `RICEAN_K = NOT_IDENTIFIABLE`. Persistence is not physical reflector lifetime. See `channel_level_statistics.csv` and `persistence_duration_statistics.csv`.

## 7. Stage4 selection-effect analysis

The canonical Stage4 result is `MATERIAL_DIFFERENCE`, which is treated as a selection effect rather than a failure. The closure compares the 100 strict-confirmed Stage4 paths with the 783-observation Stage3 primary population. The linked Stage3 subset contains 98 observations for the persistence proxy; Stage4 itself has no physical persistence field.

Stage4 differences are quantified for delay, Doppler, power, environment composition, elevation-ready composition, and the linked Stage3 algorithm-track persistence proxy. The known 100-ms joint selection and candidate-cap mechanisms are retained as design explanations, not post-hoc corrections. Stage4 is not external truth.

Parameter-level material-difference flags: 2 of 3. See `stage4_selection_analysis.csv` and the r3 Stage3/Stage4 sensitivity tables.

## 8. Continuous elevation decision

The continuous-elevation decision for a future conditional model is `CONDITIONAL`. Evidence classes are recomputed per environment×parameter in `continuous_elevation_evidence.csv`: `ROBUST` means the scene-block slope interval excludes zero, `WEAK` means the interval includes zero but diagnostics are directionally coherent, `INCONSISTENT` means rank and slope directions disagree, and `INSUFFICIENT` means support is inadequate.

| Environment | Parameter | Evidence |
|---|---|---|
| Urban | excess_delay_samples | WEAK |
| Urban | doppler_offset_hz | INCONSISTENT |
| Urban | relative_power_db | ROBUST |
| Special Reflective | excess_delay_samples | INSUFFICIENT |
| Special Reflective | doppler_offset_hz | INSUFFICIENT |
| Special Reflective | relative_power_db | INSUFFICIENT |
| Mountain/Valley | excess_delay_samples | ROBUST |
| Mountain/Valley | doppler_offset_hz | ROBUST |
| Mountain/Valley | relative_power_db | WEAK |
| Highway/Open | excess_delay_samples | INSUFFICIENT |
| Highway/Open | doppler_offset_hz | INSUFFICIENT |
| Highway/Open | relative_power_db | INSUFFICIENT |

## 9. Joint dependence and AI motivation

The existing rank-Gaussian dependence diagnostics do not support treating all three parameters as independent. The future joint-density motivation is `STRONG` because the global delay–relative-power association is material and environment-level dependence is available, while cell-level dependence remains support-gated. This motivates a future conditional joint model only if Phase 2 is separately authorized; it does not authorize training here.

Pairwise and scope-specific interpretations are in `joint_dependence_interpretation.csv`.

## 10. Robustness and data gaps

The robustness matrix compares primary weighted observations, raw clustered observations, algorithm-track medians, Stage4 sensitivity, scene-block bootstrap, run-block sensitivity, and grouped LOSO validation. It is intended for direct reuse in paper limitations and discussion.

| Support class | Cell count |
|---|---:|
| `DATA_SUPPORTED` | 5 |
| `SPARSE_PARTIAL_POOLING` | 4 |
| `PRIOR_DOMINANT` | 2 |
| `NO_DIRECT_SUPPORT` | 1 |

Every cell and the four separate data-gap decisions are in `support_gap_decision.csv`. Current bounded claims are possible with limitations; complete 12-cell modeling and continuous-elevation generalization remain conditional; Highway/Open–LOW has no direct Stage3 support and receives no synthetic fill.

## 11. Paper-ready figure and table plan

The source plan ranks compact evidence by scientific question. VTC remains a narrower path-characterization paper: fitted stochastic channel modeling, complete synthetic channel generation, and Ricean-K modeling are not automatically VTC claims.

- **Figure 1 — Measurement to SAGE to statistical closure workflow**: `CORE`; Use only as a workflow schematic; not a new experiment.
- **Figure 2 — Environment × elevation support matrix**: `CORE`; Keep Highway/Open–LOW visibly empty.
- **Figure 3 — Excess-delay distributions**: `CORE`; Use fitted curves for journal/thesis; VTC may use descriptive CDF only.
- **Figure 4 — Signed relative-Doppler distributions**: `CORE`; Avoid treating relative Doppler as absolute physical scatterer velocity.
- **Figure 5 — Relative-power distributions**: `CORE`; Use dB relative power; no absolute RF claim.
- **Figure 6 — Derived RMS delay and Doppler spread**: `SUPPLEMENTARY`; Label conditional RMS and center-level scope.
- **Figure 7 — Joint parameter dependence**: `SUPPLEMENTARY`; Do not show unsupported cell covariance as universal.
- **Figure 8 — Stage3 versus Stage4 selection sensitivity**: `CORE`; Stage4 is not external truth.
- **Figure 9 — Continuous-elevation exploratory trends**: `SUPPLEMENTARY`; Current decision is conditional; bands remain formal.

Minimal tables:
- **Table 1 — Frozen population and statistical contract**: `CORE`; Define observations, tracks, weights, hierarchy, and uncertainty.
- **Table 2 — Environment/elevation effect and robustness summary**: `CORE`; Present bounded effect directions and sensitivity classifications.
- **Table 3 — Environment × elevation support/data gaps**: `CORE`; Make direct, sparse, prior-dominated, and empty cells explicit.
- **Table 4 — Channel-level derived statistics**: `SUPPLEMENTARY`; Separate center/channel diagnostics from path-level fitted parameters.

## 12. Plain-language answers and forbidden claims

1. Supported trends are bounded, measurement-derived differences in the three path parameters; no universal propagation law is established.
2. Environment differences are parameter-specific and partial; unsupported comparisons remain `NO_ROBUST_DIFFERENCE` or `INCONCLUSIVE`.
3. Elevation effects are assessed only through LOW/MID/HIGH; continuous elevation is conditional.
4. Environment×elevation interaction is not uniformly established; it is reported per parameter and environment with sparse-cell limitations.
5. Global path-level families are delay Lognormal, signed Doppler Normal, and relative-power Normal under weighted grouped LOSO selection.
6. Center/channel statistics are available conditionally as algorithm-observed diagnostics, not total-channel truth.
7. Delay and relative power show meaningful global rank dependence; cell-level dependence is support-gated.
8. Dependence treatment is sensitive enough that scene/run clustering and track-median comparisons remain required.
9. Stage4 is materially different from Stage3 and therefore is a selection-sensitivity baseline only.
10. Main limitations are sparse/prior cells, empty Highway/Open–LOW, Stage4 selection, lack of physical reflector identity, no phase/main-path reference for K, and limited independent scenes.
11. Existing 10.23 MHz evidence is sufficient for bounded traditional journal/thesis claims with limitations, not unrestricted channel generalization.
12. Do not claim no physical multipath, physical reflector lifetime, Ricean K, absolute RF power, complete 12-cell coverage, universal elevation law, or that Stage4 is external truth.

## Commander decision block

```text
PHASE_1_TRADITIONAL_MODEL_BUILD = COMPLETE
PHASE_1_SCIENTIFIC_CLOSURE = PASS_WITH_LIMITATIONS
JOURNAL_TRADITIONAL_MODELING_EVIDENCE = READY_WITH_LIMITATIONS
MASTER_THESIS_TRADITIONAL_MODELING_EVIDENCE = READY_WITH_LIMITATIONS
ENVIRONMENT_EFFECT = INCONCLUSIVE
ELEVATION_EFFECT = PARTIAL
ENVIRONMENT_ELEVATION_INTERACTION = PARTIAL
AI_JOINT_DENSITY_MOTIVATION = STRONG
CONTINUOUS_ELEVATION_FOR_PHASE2 = CONDITIONAL
PROCESS_20_46_MHZ_BEFORE_PHASE2 = CONDITIONAL
NEW_DATA_COLLECTION_BEFORE_PHASE2 = CONDITIONAL
```

All closure outputs are in the new-only namespace `E:\GNSS_Multipath_Project\dataset_generation_logs\channel_modeling\phase1_scientific_closure_20260830_r1`. No MATLAB/SAGE/batch process, raw IQ read, 20.46 MHz processing, AI training, production request, or modification of r3/r1/r2/Stage4 was performed.
