# GNSS Academic Channel Modeling Master Plan

## Mainline 10.23 MHz three-layer route (Commander authorization, 2026-10-24)

This dated Mainline route governs the new 83-run / 13-scene Stage2 population;
the older Stage3 r3/Phase-1 results below remain historical, bounded evidence
for their different population. Do not transfer their fitted parameters.

| Layer | Question, output and status | Prerequisites and acceptance |
|---|---|---|
| 1: SAGE path-parameter statistics | Excess-delay, signed relative-Doppler and relative-power marginals; power-delay dependence, selected-window MPC counts and cross-scene baseline. **EXPLORATORY_V0_COMPLETE_WITH_LIMITATIONS** under explicit 2026-10-24 authorization. | Verified all-Stage2 ledger; preserve all 8,914 MPC; exact identities, quality/fit-failure accounting, scene-LOSO and whole-scene uncertainty, reproducible real-data tables/figures and independent review. Formal Gate G is not granted by the V0 execution status. |
| 2: Environment, satellite geometry and vehicle-motion conditions | Global/Urban and other environment comparisons; continuous elevation and position descriptors, source/missingness/selection sensitivity. **INITIAL_EXPLORATION**, later extension. | Distinguish GSV-measured and ephemeris-derived elevation, including GGA/zero-height sources. Scene support and held-out results must justify shared/hierarchical or environment-specific parameters; two-scene environments remain cautious/descriptive. |
| 3: Channel structure, temporal evolution and CIR validation | Window CIR/PDP features, SAGE/CIR consistency, selected/nonselected-window differences, path counts/structure/clusters and temporal variation where supported. **WAITING_FOR_TASK5_AND_GATE_EF**. | Complete Task5 with independent Gate E/F, exact run/window association and source-bound read-back QA before full structural validation; no physical path tracking or random-cluster claim by inference. |

The progression is one engineering objective: parameter baseline → conditional
explanation → channel structure with CIR evidence. SAGE-only exploratory V0
does **not** wait for CIR and does not grant Gate E/F or full Gate G. Stage3/4
are attributes, not population filters. Outer validation holds entire scenes;
overlapping windows and same-scene PRNs are repeated observations. The current
36 spatial summaries remain insufficient to estimate independent route units.
Phase-2 generative AI remains planned-only. Implementation and actual outcomes:
`docs/superpowers/plans/2026-10-24-mainline-1023-stage2-v0.md`.

Actual V0 evidence: `reports/data_consolidation_20261003/mainline_1023_model_v1/v0_20261024T132210Z/v0_model_report.md`.
All 8,914 MPC are retained. Global 13-scene LOSO favors Lognormal among the
delay candidates; Normal/Student-t remain competitive for signed Doppler and
relative power. Training AICc and held-out power rankings differ. Same-scene
Urban-vs-global paired comparisons have negative mean deltas for all nine
candidate combinations, so the evidence does not justify an Urban-specific
parameter set yet. Pooled power-delay Spearman rho=-0.616410, slope=-8.209394
dB/chip with whole-scene bootstrap 95% interval [-14.288980,-3.852434]; linear
R²=0.055343 and large scene differences prevent a universal linear-law claim.
Three Student-t numerical failures and 36 support-limited environment-fold
records are preserved. The three layers remain the same route; completion of
this exploratory baseline does not complete the conditional/structural layers.

## Scope and governing decision

This document governs the long-term academic channel-modeling route. The
canonical traditional model is the frozen, QA-passed:

```text
environment_elevation_stage3_path_model_v1_20260829_r3
```

It is a measurement-derived, conditional model of Stage3 reliable/persistent
path observations. It is not a physical-reflector census or an unrestricted
propagation truth model. The current primary statistical unit is
`WEIGHTED_OBSERVATION`, with weight `1 / algorithm_track_size`; inference is
clustered by scene/run and uses scene-block bootstrap uncertainty.

The canonical population is 783 academic Stage3 observations, 445 centers,
366 algorithm-level tracks, 716 elevation-ready observations, 50 runs, 12
scenes, and 18 PRNs. Stage4 strict-confirmed paths are a high-confidence
validation subset only; they do not select or tune the Stage3 model. Ricean K
remains not scientifically identifiable from this evidence.

The selected global marginal families are excess delay `Lognormal`, signed
relative Doppler `Normal`, and relative power `Normal`. Gaussian Copula
dependence is retained only at global, environment, and support-gated cell
levels; no independent covariance fit is claimed for every cell. The closure
uses scene-block bootstrap, run-level sensitivity, and grouped LOSO evidence.

## Phase status

```text
PHASE 1 = Traditional Statistical Modeling + Scientific Closure
PHASE 2 = AI Conditional Generative Modeling

PHASE_1_MODEL_BUILD = COMPLETE
PHASE_1_TRADITIONAL_MODEL_BUILD = COMPLETE_WITH_LIMITATIONS
PHASE_1_SCIENTIFIC_CLOSURE = PASS_WITH_LIMITATIONS
JOURNAL_TRADITIONAL_MODELING_EVIDENCE = READY_WITH_LIMITATIONS
MASTER_THESIS_TRADITIONAL_MODELING_EVIDENCE = READY_WITH_LIMITATIONS
LONG_TERM_MANUSCRIPT_RESULTS_SYNCHRONIZATION = PENDING / IN_PROGRESS

PHASE_2 = PLANNED_ONLY
PHASE_2_EXECUTION_AUTHORIZED = NO
```

The Phase‑1 model build and scientific closure are complete with limitations.
The effect interpretation, environment/elevation characterization,
interaction analysis, channel-statistic support, Stage4 selection analysis,
robustness matrix, data-gap decisions, and publication evidence plan have
received independent QA. The work-package list below is retained as the
closure record; it is not a statement that the canonical model is still
pending.

## Frozen Phase‑1 input and protection boundary

Phase‑1 closure reads only the canonical r3 model namespace and its auditable
source tables:

```text
dataset_generation_logs/channel_modeling/environment_elevation_stage3_path_model_v1_20260829_r3/
```

The formal elevation interface is fixed as `LOW=[0,30)`, `MID=[30,60)`, and
`HIGH=[60,90]`. All 12 environment×elevation cells remain represented;
`Highway/Open–LOW` remains `NO_DIRECT_SUPPORT` and must never receive a
synthetic empirical fill. The r3 classifications are 5
`DATA_SUPPORTED`, 4 `SPARSE_PARTIAL_POOLING`, 2 `PRIOR_DOMINANT`, and 1
`NO_DIRECT_SUPPORT` cell.

Phase‑1 closure must not:

- rebuild or modify r3, r2, r1, the Stage4 model, historical QA, or existing SAGE artifacts;
- rerun SAGE, invoke MATLAB or batch production, read raw IQ, or process 20.46 MHz;
- create production requests, train an AI model, or expand the frozen queue;
- interpret algorithm tracks as physical reflectors or persistence as physical lifetime;
- compute Ricean K without a newly justified main/reference amplitude-and-phase definition.

The completed closure outputs use the new-only namespace:

```text
dataset_generation_logs/channel_modeling/phase1_scientific_closure_20260830_r2/
```

The earlier `phase1_scientific_closure_20260830_r1_superseded/` namespace is
retained for audit history. It is not a current evidence source.

## Phase‑1 scientific closure work packages

The following work packages were completed for the canonical r3/r2 closure;
future extensions remain separately gated by the evidence limitations.

1. Quantify environment, elevation, and environment×elevation effects for excess delay, signed relative Doppler, and relative power using weighted contrasts, model-derived quantiles, scene-block intervals, and grouped LOSO evidence.
2. Characterize each environment without forcing a difference where evidence supports `NO_ROBUST_DIFFERENCE`.
3. Classify LOW/MID/HIGH elevation effects and retain continuous elevation as exploratory only.
4. Separate path-level distributions from center/channel-level derived statistics, including conditional RMS delay/Doppler spread, power-weighted centroids, component counts, relative powers, and algorithm-observed persistence.
5. Quantify Stage4 strict-confirmation selection effects without treating Stage4 as external truth.
6. Interpret Gaussian-copula dependence and determine whether a future conditional joint density has strong, moderate, or weak scientific motivation.
7. Build the robustness matrix across weighted observations, raw clustered observations, algorithm-track medians, Stage4, scene/run blocks, and LOSO validation.
8. Decide separate data requirements for bounded journal claims, complete 12-cell coverage, continuous-elevation generalization, and future AI.
9. Prepare ranked CORE/SUPPLEMENTARY/THESIS_ONLY figure and table source data while respecting the narrower VTC path-characterization scope.
10. Produce the Phase‑1 scientific closure report and independent QA result, then stop.

## Phase‑2 provisional plan only

Phase 2, if separately authorized after Phase‑1 closure, would target
conditional generative modeling of:

```text
delay / Doppler / relative power | environment, elevation
```

The baseline candidate is a Mixture Density Network and the primary candidate
is a Conditional Normalizing Flow. Conditions may be either environment plus
continuous elevation or environment plus LOW/MID/HIGH, selected only from the
Phase‑1 continuous-elevation decision. Evaluation may include grouped
leave-one-scene-out conditional likelihood, Wasserstein distance, CDF error,
joint-dependence reproduction, tail reproduction, and Stage4 high-confidence
validation. No architecture is frozen and no training is authorized.

## Phase‑2 GO/NO-GO condition

AI is justified only if Phase‑1 demonstrates a meaningful unresolved problem
for the traditional model, such as nonlinear continuous-elevation dependence,
non-Gaussian or nonlinear joint dependence, poor cross-scene generalization,
important tail mismatch, or meaningful interaction not captured by coarse
elevation bands. AI is not added merely because it is available or fashionable.

## Evidence and paper boundary

The long-term journal/thesis closure may use the fitted traditional model and
its limitations. The VTC2027-Spring paper remains a narrower
measurement-to-SAGE path-characterization paper: fitted stochastic channel
modeling, complete channel generation, Ricean-K modeling, and synthetic
channel generation are not automatically VTC results. Any VTC claim must be
rebuilt from its current evidence matrix and QA-passed artifacts.

## Execution order and stop condition

```text
1. Freeze r3 as canonical Phase‑1 model
2. Complete Tasks A–J scientific closure
3. Prepare publication evidence plan
4. Create Phase‑1 scientific conclusion report
5. Independent QA
6. Update this Master Plan with actual Phase‑1 conclusion
7. Leave Phase 2 PLANNED_ONLY
8. STOP and await Commander instruction
```

## Phase‑1 closure conclusion (2026-08-30)

The canonical r3 model passed the closure analysis and independent QA with
limitations. The evidence is ready for bounded traditional-modeling journal
and master-thesis use. Environment effects are `INCONCLUSIVE` at the global
three-parameter decision level; formal LOW/MID/HIGH elevation effects are
`INCONCLUSIVE`; environment×elevation interaction is `PARTIAL` because a
few difference-in-differences are supported while sparse/prior-dominated
cells prevent a uniform claim. The global joint dependence evidence makes
the motivation for a future conditional joint density `STRONG`, but this is
not authorization to train it. Continuous elevation remains `CONDITIONAL`.

The model results are complete for this bounded Phase‑1 scope; synchronization
of the results into the long-term manuscript Results section remains pending.

Machine-readable closure tables, report, receipt, and independent QA are in:

```text
dataset_generation_logs/channel_modeling/phase1_scientific_closure_20260830_r2/
docs/ENVIRONMENT_ELEVATION_STAGE3_ACADEMIC_MODEL_V1_R3_REPORT.md
docs/PHASE1_TRADITIONAL_CHANNEL_MODELING_SCIENTIFIC_CLOSURE.md
```

The audited completion gate is:

```text
PHASE_1_TRADITIONAL_MODEL_BUILD = COMPLETE
PHASE_1_TRADITIONAL_STATISTICAL_MODELING = COMPLETE_WITH_LIMITATIONS
PHASE_1_SCIENTIFIC_CLOSURE = PASS_WITH_LIMITATIONS
JOURNAL_TRADITIONAL_MODELING_EVIDENCE = READY_WITH_LIMITATIONS
MASTER_THESIS_TRADITIONAL_MODELING_EVIDENCE = READY_WITH_LIMITATIONS
ENVIRONMENT_EFFECT = INCONCLUSIVE
ELEVATION_EFFECT = INCONCLUSIVE
ENVIRONMENT_ELEVATION_INTERACTION = PARTIAL
AI_JOINT_DENSITY_MOTIVATION = STRONG
CONTINUOUS_ELEVATION_FOR_PHASE2 = CONDITIONAL
PROCESS_20_46_MHZ_BEFORE_PHASE2 = CONDITIONAL
NEW_DATA_COLLECTION_BEFORE_PHASE2 = CONDITIONAL
```

Phase 2 remains `PLANNED_ONLY` and `PHASE_2_EXECUTION_AUTHORIZED = NO`.
No MATLAB/SAGE task, production request, raw-IQ read, r3/Stage4
modification, 20.46 MHz processing, new data collection, or AI training was
performed. The next action requires a new Commander decision.
