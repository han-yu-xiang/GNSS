# GNSS 完整多径参数统计建模：总体目标、工作包与验收路线图

**唯一长期建模路线与工作包状态来源：** 本文件。

**最新主线状态核实：** 2026-10-24（Asia/Shanghai）；Task 5 的状态样本见工程交接手册第101节。

**状态职责：** 工程执行、release、QA、receipt 和生产状态以 `docs/GNSS_SAGE_ENGINEERING_HANDOFF_CURRENT.md` 为唯一工程来源；论文事实与科学解释以 `docs/GNSS_SAGE_PAPER_HANDOFF_CURRENT.md` 为唯一论文来源。本文件负责最终研究目标、长期路线、WP0–WP6、依赖及其状态；其他文件只链接本文件或记录执行细节，不建立竞争性的总计划。

WP编号是长期研究工作包编号，与 Mainline CIR 实施计划中的 Task 1–7、SAGE Stage 0–4 不是同一套编号。

## Mainline 10.23 MHz three-layer route (Commander authorization, 2026-10-24)

This dated Mainline route governs the new 83-run / 13-scene Stage2 population;
the older Stage3 r3/Phase-1 results below remain historical, bounded evidence
for their different population. Do not transfer their fitted parameters.

| Layer | Question, output and status | Prerequisites and acceptance |
|---|---|---|
| 1: SAGE path-parameter statistics | Excess-delay, signed relative-Doppler and relative-power marginals; power-delay dependence, selected-window MPC counts and cross-scene baseline. **COMPLETED_WITH_LIMITATIONS** for exploratory V0 under explicit 2026-10-24 authorization. | Verified all-Stage2 ledger; preserve all 8,914 MPC; exact identities, quality/fit-failure accounting, scene-LOSO and whole-scene uncertainty, reproducible real-data tables/figures and independent review. Formal Gate G is not granted by the V0 execution status. |
| 2: Environment, satellite geometry and vehicle-motion conditions | Global/Urban and other environment comparisons; continuous elevation and position descriptors, source/missingness/selection sensitivity. **IN_PROGRESS**: initial exploration only. | Distinguish GSV-measured and ephemeris-derived elevation, including GGA/zero-height sources. Scene support and held-out results must justify shared/hierarchical or environment-specific parameters; two-scene environments remain cautious/descriptive. |
| 3: Channel structure, temporal evolution and CIR validation | Window CIR/PDP features, SAGE/CIR consistency, selected/nonselected-window differences, path counts/structure/clusters and temporal variation where supported. **PENDING_DEPENDENCY** on Task 5 and independent Gate E/F. | Complete Task5 with independent Gate E/F, exact run/window association and source-bound read-back QA before full structural validation; no physical path tracking or random-cluster claim by inference. |

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

## Final scientific objective

Build a reproducible, observation-derived statistical model of GNSS multipath
that explains measured parameter distributions and their supported condition
dependence, then validates the resulting channel description against real
CIR/PDP evidence and independent scenes. The final model may include excess
delay, signed relative Doppler, relative power and complex alpha; their joint
relationships; window-level MPC counts and path structure; environment,
satellite-elevation, vehicle-motion and spatial context; and temporal change
where the observations support it. It must report provenance, uncertainty,
selection mechanisms, applicable populations and limitations. Final model
families and physical interpretations remain open until evidence justifies
them; a plan, fitted marginal or completed CIR batch alone is not the complete
model.

## Work packages WP0–WP6

These packages organize the long-term Mainline modeling objective. Statuses
below were reconciled against the dated V0 report, existing geometry and
Stage2-ledger evidence, current Mainline implementation plan and the latest
available Task 5 local status snapshot. The Task 5 process fields were
incomplete in that snapshot; see WP4 and the Engineering Handoff before any
operational decision.

| WP | Status (controlled vocabulary) | Scope and verified state | Dependency and acceptance boundary |
|---|---|---|---|
| WP0 — Data baseline and production-state management | `IN_PROGRESS` (continuous) | Maintain identity-frozen SAGE cohort, CIR queue, exclusions, Stage2 ledger, geometry/trajectory overlays, provenance, hashes and independently accepted QA. Keep SAGE and CIR denominators distinct. | Foundation for WP1–WP6. Each result must resolve to the exact dataset/version and task identity; production status is timestamped from current receipts/snapshots, never inferred from an old handoff. |
| WP1 — Layer 1 SAGE parameter statistics V0 | `COMPLETED_WITH_LIMITATIONS` | Real-data exploratory V0 retains 8,914 MPC from 83 runs / 13 scenes and 7,847 selected windows. Global scene-LOSO favored Lognormal among tested delay marginals; Normal/Student-t remain competitive for signed Doppler and relative power. A negative pooled power-delay association is present, but low linear R² and scene heterogeneity do not establish a universal law. Urban-specific gains were not supported by paired same-scene comparisons. | Keep the V0 report, tables, fit failures and support-limited folds immutable. This status is only the authorized exploratory baseline; formal Gate G and the complete channel model are not passed. |
| WP2 — Layer 1 robustness and statistical closure | `IN_PROGRESS` | V0 already supplies scene-level LOSO, whole-scene bootstrap for the power-delay slope, marginal comparisons, count summaries and initial association checks. Remaining work is a bounded robustness closure: sensitivity to scene support and tails, parameter dependence, count-model candidates and uncertainty/model-rank stability. | Uses the frozen Stage2-selected population; can proceed before CIR completion. Do not treat 8,914 paths or overlapping windows as independent scenes; retain failed fits and unsupported folds. |
| WP3 — Layer 2 environment, geometry and motion conditions | `IN_PROGRESS` | Initial overlays and descriptions distinguish GSV measured from ephemeris-derived elevation, GGA height from zero-height assumptions, and position-source coverage. Existing 36 spatial summaries remain insufficient to support an independent spatial range/segment claim. Formal condition models are not complete. | Can proceed on existing Stage2 data without waiting for WP4. Use scene-held-out evaluation; preserve missingness, provenance and support. Do not extrapolate missing angles/positions or create separate environment models without held-out benefit and adequate scene support. |
| WP4 — CIR/PDP production and quality acceptance | `IN_PROGRESS` | The latest hourly snapshot at 2026-10-24 22:10 +08 recorded Task 5 and audit `RUNNING`, 9/80 complete, 0 newly reported PASS in the prior hour, current `run_20261003_F1023_V120_D0121_P2_G28_ch6`, elapsed 4,350 s, 362 GiB free, monitor `FRESH` with age 5 min at collection, zero reported storage errors in the prior hour, and no completion or stop receipt. MATLAB/Coordinator status booleans and last-PASS identity were null; the snapshot listed MATLAB PIDs 42528/47340 but supplied no Coordinator PID. The last valid progress timestamp was 20:57:42 +08 and excludes MAT/HDF5 file times. An adjacent 21:10 snapshot had recorded G25/ch5 as the last PASS at 20:57:24 +08. This is a timestamped sample, not a fresh process-owner check or a stall finding. | Preserve the immutable serial release, successful outputs and receipts; never rerun accepted pilots or silently retry failures. Gate E requires reconciliation of the frozen 83-identity cohort, the three retained PASS pilots, all 80 serial-batch task receipts, the batch audit and its completion receipt. Gate F then requires exact run/window identity, retention of all Stage2 MPC, HDF5 read-back and independent SAGE/CIR/PDP consistency checks. Task 5 completion alone passes neither gate automatically. |
| WP5 — Complex alpha and path-attribute integration | `IN_PROGRESS` (preparation only; real batch delivery unverified) | Candidate `scripts/channel_modeling/export_stage2_complex_alpha.m` and its test file exist in the isolated worktree but are untracked; their existence is not release-pinned implementation, production output, or QA evidence. No accepted batch alpha receipt or independently verified alpha dataset was found in the authoritative status record reviewed for this update. | May progress alongside WP2/WP3 where it does not contend with Task 5 resources. Bind run/window/path identity and source hashes; validate complex values, ordering and provenance. Keep window-normalized alpha and receiver-calibration limitations explicit. |
| WP6 — Integrated channel model and final independent validation | `PENDING_DEPENDENCY` | No Mainline integrated model, complete CIR feature association or final Gate G acceptance is claimed. The older Stage3 r3 Phase-1 model remains a separate completed-with-limitations population and is not a substitute for this Mainline model. | Requires WP1 plus accepted WP2–WP5 evidence. Select final model only after support and diagnostics; validate by holding out entire scenes, preserve uncertainty, and document what the model cannot establish. Phase-2 generative AI is a separate planned-only decision. |

## Work-package dependencies and concurrency

- WP0 supplies identity, source/version and status controls for every package.
- WP1 provides the exploratory baseline used by WP2, WP3 and ultimately WP6.
- WP2 and WP3 can proceed in parallel on the existing Stage2 cohort; neither must wait for the entire CIR batch.
- WP4 proceeds under its already-authorized serial release. WP4's real CIR/PDP associations and acceptance evidence feed WP6 only after independent Gate E/F checks.
- WP5 may proceed alongside WP2/WP3 when input provenance and storage/compute resources permit; its real outputs need their own independent acceptance before WP6 consumes them.
- WP6 starts only when the required WP2–WP5 inputs and validation evidence are available. Dependencies are evidence gates, not a requirement to serialize unrelated analysis.

## Acceptance, scientific boundaries and state vocabulary

Use only these work-package statuses: `NOT_STARTED`, `IN_PROGRESS`,
`BLOCKED`, `PENDING_DEPENDENCY`, `COMPLETED`, and
`COMPLETED_WITH_LIMITATIONS`. A status applies to the named scope and must
cite its evidence and as-of time. Keep implementation, actual production,
QA acceptance and scientific conclusion as separate sub-states; for example,
code present does not mean output produced, output produced does not mean QA
passed, and a model fit does not mean independent validation passed.

- Preserve all 8,914 MPC in the current Stage2 candidate population. The
  7,847 selected windows are conditional on the Stage1/Stage2 selection
  pipeline from 285,752 Stage0-valid windows; unselected windows are not
  zero-MPC observations.
- Use `(run_id, window_id, path_id)` where path-level joins apply, and exact
  `(run_id, window_id)` for window overlays. Keep scene as the outer
  validation and uncertainty unit; overlapping windows and same-scene PRNs
  are repeated observations.
- Stage3/Stage4 are attributes or specified validation subsets, not automatic
  filters. Distinguish GSV-measured and ephemeris-derived elevation and keep
  GGA/zero-height provenance and missing values explicit.
- Treat relative power as relative, not calibrated absolute receive power.
  Do not infer physical reflector identity or lifetime from path numbering or
  temporal persistence alone. Do not claim a physical propagation law from a
  weak pooled association.
- `COMPLETED` requires the scope's actual artifacts and acceptance evidence;
  use `COMPLETED_WITH_LIMITATIONS` when results are valid only within stated
  limitations. Use `BLOCKED` for an identified blocker and
  `PENDING_DEPENDENCY` when a prerequisite is not yet accepted.

## Long-term update and handoff protocol

At the start of each substantial task, read this plan and the current
Engineering Handoff, then read the relevant implementation plan, manifest,
receipt, QA and artifact. Identify its WP, goal, dependencies, prohibited
actions and status evidence. Check the evidence timestamps; do not reuse a
historical sample as live state. If documents and current evidence disagree,
resolve the facts first and update the affected current record before
continuing.

At task completion, record the actual scope, file/output paths, code and data
versions, tests, production status, QA status, scientific result, limitations
and next dependency. Update this Master Plan's WP state and the Engineering
Handoff. Update the Paper Handoff when research questions, claims, results or
paper status change; update `PAPER_WORKSPACE_INDEX.md` only when paper asset
structure changes. Retain unfinished, failed, unsupported and blocked work
with reasons. A plan is not execution, a passing test is not real-data
acceptance, and one gate does not complete its downstream package.

At handoff, answer: the final objective; active and accepted WPs with evidence
dates; completed artifacts and their limits; work still running or waiting;
the next authorized action; and production/data that must not be touched.
Append dated evidence; do not replace prior experiment receipts or turn a
temporary status snapshot into a new status authority.

## Historical Stage3 r3 model and Phase‑1 scope (separate population)

This section records the separately completed Stage3 r3 Phase‑1 population;
it does not replace or provide parameters for the current Mainline Stage2
route and WP0–WP6 status above. Its canonical traditional model is the frozen,
QA-passed:

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

## Historical Phase‑1 / Phase‑2 status for Stage3 r3

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
