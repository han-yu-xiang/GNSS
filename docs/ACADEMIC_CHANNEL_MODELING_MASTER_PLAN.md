# GNSS 完整多径参数统计建模：总体目标、工作包与验收路线图

**唯一长期建模路线与工作包状态来源：** 本文件。

**最新主线状态核实：** 2026-10-28（Asia/Shanghai）；WP2 与 WP3 均为 `COMPLETED_WITH_LIMITATIONS`，WP3 独立科学审阅为 `PASS_WITH_LIMITATIONS`；Task 5 的 23:30 +08 只读样本见本计划第106节及工程交接手册第106节。所有 Task 5 状态均为时间点证据。

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
below were reconciled against the dated V0/WP2/WP3 reports, geometry and
Stage2-ledger evidence, and a direct read-only Task 5 process/audit/task sample
at 2026-10-28 22:11 Asia/Shanghai. Task 5 is a timestamped point-in-time
sample; recheck before any operational decision.

| WP | Status (controlled vocabulary) | Scope and verified state | Dependency and acceptance boundary |
|---|---|---|---|
| WP0 — Data baseline and production-state management | `IN_PROGRESS` (continuous) | Maintain identity-frozen SAGE cohort, CIR queue, exclusions, Stage2 ledger, geometry/trajectory overlays, provenance, hashes and independently accepted QA. Keep SAGE and CIR denominators distinct. | Foundation for WP1–WP6. Each result must resolve to the exact dataset/version and task identity; production status is timestamped from current receipts/snapshots, never inferred from an old handoff. |
| WP1 — Layer 1 SAGE parameter statistics V0 | `COMPLETED_WITH_LIMITATIONS` | Real-data exploratory V0 retains 8,914 MPC from 83 runs / 13 scenes and 7,847 selected windows. Global scene-LOSO favored Lognormal among tested delay marginals; Normal/Student-t remain competitive for signed Doppler and relative power. A negative pooled power-delay association is present, but low linear R² and scene heterogeneity do not establish a universal law. Urban-specific gains were not supported by paired same-scene comparisons. | Keep the V0 report, tables, fit failures and support-limited folds immutable. This status is only the authorized exploratory baseline; formal Gate G and the complete channel model are not passed. |
| WP2 — Layer 1 robustness and statistical closure | `COMPLETED_WITH_LIMITATIONS` | Bounded closure completed 2026-10-25 from pinned V0 MPC/window extracts and saved LOSO folds; no V0 refit. Independent scientific acceptance on 2026-10-25 recomputed saved-fold scores/ranks, tail diagnostics, all power-delay folds and all selected-count folds with no numerical mismatch. Global Lognormal delay ranked first in 13/13 held-out scenes; Doppler/power ranks varied. Tail support is limited for 324/1,026 records. Negative power-delay slope direction held in 13/13 folds, but conditional prediction did not improve. Count candidates do not justify replacing the empirical table; NB2 reaches a mean-at-infinity boundary in all 13 folds. | Results: `reports/data_consolidation_20261003/mainline_1023_model_v1/wp2_20261025T074332Z/`; acceptance: `reports/data_consolidation_20261003/mainline_1023_model_v1/wp2_independent_acceptance_20261025T151500Z/`. All four analyses pass computational checks with limitations; overlapping LOSO training sets mean scene-resampled intervals are descriptive fold-sensitivity summaries, not independent-experiment confidence intervals. Results remain descriptive and conditional on Stage2 selection; formal Gate G/model acceptance is not granted. |
| WP3 — Layer 2 environment, geometry and motion conditions | `COMPLETED_WITH_LIMITATIONS` (independent review `PASS_WITH_LIMITATIONS`) | Bounded M0/M1/M2 scene-LOSO reconciled 8,914 MPC / 7,847 selected windows / 13 scenes; core Urban 6 scenes and Mountain/Valley 3. Lognormal delay ranked first 9/9; Doppler Student-t 6/9; relative-power Student-t and Normal 4/9 each. Independent review recommends per-parameter global M0 baselines; M1 is not a stable out-of-scene gain; GSV elevation is retained only as an exploratory relative-power candidate. | Analysis: `reports/data_consolidation_20261003/mainline_1023_model_v1/wp3_20261028T140100Z/`; independent review: `reports/data_consolidation_20261003/mainline_1023_model_v1/wp3_independent_review_20261028/WP3_独立科学审阅与模型选型报告.md`. Validator PASS; focused tests 18/18; direct review checked 891 score rows / 810 pairs with zero identity, delta, or fold-leakage mismatches. Stage2-selection conditional; nine core scenes (three Mountain/Valley), overlapping LOSO training, clustered paths/windows and incomplete tails limit inference. Not Gate G/WP6 or a causal/complete physical model. |
| WP4 — CIR/PDP production and quality acceptance | `IN_PROGRESS` (direct read-only sample 2026-10-28 23:30 +08) | Release `mainline_1023_cir_v1_20261028T120447205Z_task5successor43r1`, request SHA-256 `1b95146f42a2383f26bbef0bfc1679f9096f3778e67c51fa765af953f04474df`; audit `RUNNING`, 7/43 new PASS plus 37 inherited = 44/80. Current `run_20261003_F1023_V70_D0120_P9_G26_ch6`, started 23:01:45 +08; Coordinator PID 17124, worker PowerShell PID 20688, MATLAB launcher/worker PIDs 8812/21660 present. Batch scheduled task Running (LastTaskResult 267009); 30-minute monitor Ready (last result 0 at 23:05, next 23:35); hourly monitor Ready (last result 0 at 23:10, next 00:10). CPU/file progress and new System storage events were not sampled. | Point-in-time process/audit/task sample only, not completion or Gate E/F acceptance. No production process or artifact was touched. Keep Gate E/F pending until all 43 new tasks and independent output/receipt checks are complete; accepted E: exFAT risk remains. |
| WP5 — Complex alpha and path-attribute integration | `IN_PROGRESS` (preparation only; real batch delivery unverified) | Candidate `scripts/channel_modeling/export_stage2_complex_alpha.m` and its test file exist in the isolated worktree but are untracked; their existence is not release-pinned implementation, production output, or QA evidence. No accepted batch alpha receipt or independently verified alpha dataset was found in the authoritative status record reviewed for this update. | May progress alongside WP2/WP3 where it does not contend with Task 5 resources. Bind run/window/path identity and source hashes; validate complex values, ordering and provenance. Keep window-normalized alpha and receiver-calibration limitations explicit. |
| WP6 — Integrated channel model and final independent validation | `PENDING_DEPENDENCY` | No Mainline integrated model, complete CIR feature association or final Gate G acceptance is claimed. The older Stage3 r3 Phase-1 model remains a separate completed-with-limitations population and is not a substitute for this Mainline model. | Requires WP1 plus accepted WP2–WP5 evidence. Select final model only after support and diagnostics; validate by holding out entire scenes, preserve uncertainty, and document what the model cannot establish. Phase-2 generative AI is a separate planned-only decision. |

### WP2 robustness closure evidence (2026-10-25)

Prepared evidence for Commander review is the bounded report package at
`reports/data_consolidation_20261003/mainline_1023_model_v1/wp2_20261025T074332Z/`.
The CSV-only runner reused the pinned V0 fold table and input extracts
(8,914 MPC, 7,847 Stage2-selected windows, 83 runs, 13 scenes); it did not
repeat the V0 distribution fits. Independent recount verified the 0–3 selected
window count histogram `{0: 3574, 1: 1412, 2: 1081, 3: 1780}`, all 8,914 MPC
to selected-window count links, output hashes and all three pinned input hashes.
Six runs have selected windows but no MPC rows; their selected-window counts
remain represented. The 7,847 windows are conditional on Stage2 selection from
285,752 Stage0-valid windows; unselected Stage0 windows were never assigned
zero MPC.

- **Scene sensitivity:** Global excess-delay Lognormal ranked first in 13/13
  held-out scenes; Urban Lognormal ranked first in 6/6. Doppler ranks varied
  (global Normal 6/13, Student-t 5/13, Laplace 2/13); power ranks also varied
  (global Student-t 8/13, Normal 3/13, Laplace 2/13). The per-held-out-scene
  winners and all fit-parameter quartiles are in the result tables. As one
  instability example, global relative-power Student-t degrees-of-freedom
  estimates ranged from 7.60 to 5,393.86 (median 2,897.24), so its frequent
  wins do not establish a stable finite tail parameter. These are sensitivity
  summaries across overlapping LOSO training sets, not independent fits.
- **Held-out tails:** p01/p05/p10/p90/p95/p99 diagnostics use each saved
  training-fold fit. 324 of 1,026 family/scene/quantile records have fewer
  than 10 expected observations in the relevant tail. Tail adequacy is
  therefore unresolved for those records; no tail pass is claimed.
- **Power-delay:** The fitted training-fold slope is negative in all 13/13
  global LOSO folds (median -2.506 dB/chip; range -10.525 to -2.260). But the
  scene-macro conditional-minus-marginal held-out log-score delta is -0.0605
  (whole-scene bootstrap 95% interval [-0.2100, 0.0174]) and RMSE worsens by
  0.183 dB. Direction is stable in these folds; out-of-scene predictive gain
  is not demonstrated. The pooled V0 slope is not reinterpreted as causal or
  universal.
- **Selected-window counts:** The empirical scene-balanced categorical
  baseline outscored truncated Poisson by 0.1716 mean log-score units per
  scene (95% scene-bootstrap interval [-0.2501, -0.0881]). Truncated NB2 was
  close but did not establish a gain (-0.0183; interval [-0.0492, 0.0140]);
  it reached the mean-to-infinity likelihood boundary in 13/13 folds, with no
  finite mean MLE. The evidence does not justify a separate parametric count
  model now; retain the descriptive empirical count table as Stage2-selection
  conditional, not as an unconditional occurrence model.

Targeted WP2 tests passed 11/11; py_compile and an independent output recount
passed. No MATLAB/SAGE/CIR, raw IQ, MAT/HDF5 payload, Task 5 production, or real
alpha export was run. The earlier preliminary output
`wp2_20261025T073915Z/` is superseded; its NB2 finite-bound report was caught
by independent review and replaced by the explicit boundary analysis in the
accepted `wp2_20261025T074332Z/` package. The one next priority is Commander
review of this WP2 evidence; Task 5 recovery and alpha export remain separate
decisions/dependencies.

### WP2 independent scientific acceptance (2026-10-25)

An independent read-only acceptance checked the final package at
`reports/data_consolidation_20261003/mainline_1023_model_v1/wp2_20261025T074332Z/`
against its pinned Stage2 CSV inputs, V0 fold-score table, source hashes and
saved outputs. All 15 input/source/output SHA-256 entries matched. Recomputed
the 171 applicable saved-fold scores/ranks, all 1,026 held-out-tail records,
13 power-delay folds and 39 selected-count folds; output values matched within
the numerical comparison tolerance. Population keys/counts remained 8,914
MPC, 7,847 unique Stage2-selected windows, 83 runs and 13 scenes, with every
MPC linked to a selected window and histogram `{0: 3574, 1: 1412, 2: 1081,
3: 1780}`. No local recalculation package was written and no V0 or production
analysis was rerun.

All four work items are `PASS_WITH_LIMITATIONS` for computational correctness:

- **Distribution sensitivity:** global delay Lognormal ranked first in 13/13
  held-out scenes (Urban 6/6). Global Doppler winners were Normal 6,
  Student-t 5, Laplace 2; relative-power winners were Student-t 8, Normal 3,
  Laplace 2. These summaries reuse saved V0 fit parameters/scores; they are
  not independent refits or confidence intervals. Global relative-power
  Student-t degrees of freedom ranged from 7.60 to 5,393.86 (median 2,897.24),
  so frequent wins do not establish a stable finite tail parameter. Pooled
  row-wise MLEs describe the selected path-record mixture; same-scene PRNs,
  repeated/overlapping windows and path rows are dependent observations, not
  independent scene replicates.
- **Held-out tails:** p01/p05/p10/p90/p95/p99 predictions use saved
  training-fold parameters; empirical quantiles use NumPy's linear sample
  quantile convention and coverage is the held-out fraction `x <= predicted`.
  The 324/1,026 records with fewer than 10 expected tail observations are
  correctly flagged as low support. This verifies the computation, not tail
  calibration; no blanket tail-pass claim is supported.
- **Power-delay:** all 13/13 training-fold slopes are negative (median
  -2.50632, range -10.52476 to -2.25958 dB/chip). Conditional-minus-marginal
  held-out macro log-score delta is -0.06050; RMSE delta is +0.18262 dB
  (worse). The reported intervals resample the 13 LOSO fold outcomes; because
  training sets overlap in 12 of 13 scenes, these are descriptive
  fold-sensitivity intervals, not CIs from 13 independent experiments. No
  out-of-scene predictive gain is demonstrated.
- **Selected-window counts:** 7,847 unique Stage2-selected windows link to
  8,914 unique MPC identities; counts 0–3 are preserved only on that selected
  denominator. The empirical categorical baseline exceeds truncated Poisson
  by 0.17158 macro log-score units. Truncated NB2 is close (-0.01826; its
  fold-resampled interval crosses zero) but hits its mean-to-infinity
  boundary in 13/13 folds, so no finite interior mean MLE is established.
  This is not by itself proof of a code defect; present evidence does not
  justify a separate parametric count model. Neither model describes
  unselected Stage0 windows.

The focused WP2 tests were executed on 2026-10-25 23:22:31–23:22:34 +08:
11/11 passed, exit 0. Full command and stdout are retained in
`reports/data_consolidation_20261003/mainline_1023_model_v1/wp2_independent_acceptance_20261025T151500Z/`.
Tests establish covered code behavior, not scientific validity; the formula
and output checks above are separate. No calculation error requiring local
recalculation was found. No alpha export, MAT/HDF5 payload read, MATLAB/SAGE/
CIR execution, Gate G approval or formal model fitting occurred.

The sole next WP2 priority is Commander review of this acceptance and a
decision whether descriptive scene-level evidence suffices for the next
modeling gate or a separately scoped inferential analysis is needed. WP2
remains `COMPLETED_WITH_LIMITATIONS`; Gate G is not passed.

## Work-package dependencies and concurrency

- WP0 supplies identity, source/version and status controls for every package.
- WP1 provides the exploratory baseline used by WP2, WP3 and ultimately WP6.
- WP2 and WP3 can proceed in parallel on the existing Stage2 cohort; neither must wait for the entire CIR batch.
- WP4 resumed under a separately authorized, immutable partial-successor release after its preserved `FAILED_NO_RETRY` stop receipt. Its real CIR/PDP associations and acceptance evidence feed WP6 only after independent Gate E/F checks; WP2 did not change or resume that production.
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

### Task 5 stop investigation — read-only sample 2026-10-26 16:45 +08

The 16:35 local 30-minute monitor and direct process/task/audit checks show
`NEEDS_ATTENTION`, 37/80 cumulative PASS, and no active Coordinator, Runner,
or MATLAB. The current release audit still says `RUNNING`, with 25/68 tasks
completed in that release and 43 remaining. The exact current task is
`run_20261003_F1023_V70_D0120_P8_G18_ch9` (scene `F1023_V70_D0120_P8`,
G18/channel 9); the preceding PASS is G16/channel 4 at 11:04:14 +08.

The task launch record is dated 11:04:34 +08. The audit field named
`current_task_started_utc` contains `2026-10-26T11:04:30...+08:00`, so its
offset—not the misleading property name—was used for conversion. Windows
records a critical-battery event and sleep at 13:11:27 +08, then a sleep/wake
transition around 14:26:06–14:26:10 +08. The G18 worker scheduled task's
`LastRunTime` is 14:26:06 and `LastTaskResult=1`; the batch Coordinator task
also has `LastTaskResult=1`. These events strongly associate the interruption
with battery-critical sleep/wake, but the Task Scheduler Operational log is
disabled, no process-exit receipt exists, and the precise termination time,
exception, and process-level cause remain **UNKNOWN**. No matching MATLAB
Application Error or new disk/USB I/O error was found in the bounded query.

No current-release `runs/<G18_ch9>/` directory, `execution_started.json`,
MATLAB exit receipt, CIR output, or failure/PASS receipt exists. The small
task-launch record is dispatch evidence only. An older SAGE child-process
receipt for the same run identity is from the separate 49-task SAGE plan and
is not a CIR receipt. The normal coordinator catch is designed to write
`FAILED_NO_RETRY` and close the audit; because neither closure record exists,
the audit was left nonterminal by an abrupt/unhandled exit or a failed
post-failure write, but the exact path cannot be distinguished from available
evidence. The active-lock file names the former Coordinator PID, while a
read-only exclusive-open probe found no live OS handle; do not delete it.

The release pins runner SHA-256
`71d49ec0127aa3d254455abbbe39ceb8770cf7e99eb9fcfb2cdc55bd401a59e9`, while
the current runner is
`622629588a2552ae150149d5860abc6102fc0b2dadc60bdcb5f2e3643bcb5692` and its
filesystem modification time is 16:18:14 +08, after the recorded 14:26 worker
task result. This later pin drift is not evidence for the G18 failure's root
cause, but it prevents safely invoking the old release now. E: had 300.3 GiB
free; its previously accepted health warning remains unverified and was not
repaired. The only recommended Task 5 action is to keep this release and its
37 PASS results untouched until an explicitly authorized, source-pinned,
no-retry successor recovery is prepared.

## 106. Mainline Stage2 WP3 environment/geometry modeling (2026-10-28)

WP3's bounded real-data implementation and independent output reconciliation
were completed on pinned Stage2 CSV extracts. Independent scientific review is
`PASS_WITH_LIMITATIONS`; the recommended retained structure is a per-parameter
global M0 core baseline, with no accepted M1 gain and only exploratory GSV
relative-power M2. This is not formal Gate G, WP6, CIR-feature acceptance, or a
physical/causal channel claim.

- **Population and support:** 8,914 unique MPC, 7,847 unique Stage2-selected
  windows, 83 runs and 13 scenes were reconciled. Core inference is restricted
  to Urban (6 scenes, 2,927 windows, 3,698 MPC) and Mountain/Valley (3 scenes,
  1,974 windows, 2,637 MPC). Six selected-window runs with no MPC remain in
  the window denominator. The 285,752 Stage0-valid windows are not the
  denominator; unselected windows are not zero-MPC observations.
- **M0/M1/M2 and held-out results:** complete-scene LOSO covers all nine core
  scenes. M0 delay Lognormal ranks first in 9/9 folds; Doppler Student-t ranks
  first in 6/9 (Normal 2, Laplace 1); relative-power Normal and Student-t each
  rank first in 4/9 (Laplace 1). Environment-specific M1 does not show a
  stable held-out predictive gain over M0. Source-separated GSV elevation M2
  improves relative-power macro score versus M1 in the combined core results,
  but M2 versus M0 and environment-specific comparisons are mixed; this does
  not establish a universal elevation effect or causation. Ephemeris/GGA and
  zero-height strata are kept separate.
- **Independent model selection:** core M0 full-data estimates are delay
  Lognormal (`shape=0.4659688`, `scale=0.1914930 chips`), Doppler Student-t
  (`df=8.97753`, `loc=−0.4420 Hz`, `scale=62.9264 Hz`), and relative-power
  Student-t (`df=7.72049`, `loc=−8.90584 dB`, `scale=5.97587 dB`). These are
  scene/window-balanced pseudo-likelihood estimates for the nine-scene core,
  not independent-sample confidence estimates and not substitutes for WP1's
  13-scene baseline. Student-t relative power is only a provisional working
  baseline: Normal ties it at 4/9 first-place folds and its core macro score is
  within 0.014 nats/window.
- **Environment and elevation:** combined-core M1−M0 paired macro score is
  negative for every candidate family; environment splitting is not retained
  as a predictive improvement. GSV M2 relative power improves over M1 in the
  combined-core matched comparisons, but M2−M0 is mixed and per-environment
  comparisons differ. Preserve its negative GSV relative-power slope only as
  an exploratory association, not a causal or universally validated effect.
- **Tails and motion:** 2,268 held-out p05/p50/p95 diagnostics include 279
  unavailable fits and 579 nominal target-tail counts below 10. Those path-row
  counts are support flags, not effective independent sample sizes; no global
  tail pass is claimed. Vehicle motion remains descriptive: 3,372 windows
  have speed, but 144 source records are reused (one record contributes to as
  many as 96 windows); no M3 or spatial-independence model was fitted.
- **Evidence:** report and tables are in
  `reports/data_consolidation_20261003/mainline_1023_model_v1/wp3_20261028T140100Z/`;
  exact runner console is
  `reports/data_consolidation_20261003/mainline_1023_model_v1/wp3_run_20261028T140100Z_console.txt`.
  The immutable-in-practice run manifest records the pinned inputs, code and
  outputs. Independent validator status is `PASS` with no findings: output
  hashes, input pins, identities, support, full-scene folds, macro scores,
  paired identities/deltas, and held-out tails all reconcile. Focused tests
  passed 18/18 (Python 3.12; 2026-10-28 14:04:50–14:04:54 UTC; exit 0).
  Model module SHA-256 is
  `67651a6cea536df1f0d7dcd61b8da034fcc196f903b12250427fc7f1f726ac3b`;
  runner `8e4d7859473c984f4ab652b89c09ca4f4e06c59d8d7ab1a127b3ec2628c6b884`;
  independent validator `8452f4c554124011b1e44722db04152f539d855b5c66234e565620d274bff2a1`.
- **Independent scientific review:**
  `reports/data_consolidation_20261003/mainline_1023_model_v1/wp3_independent_review_20261028/WP3_独立科学审阅与模型选型报告.md`.
  Direct CSV review recomputed 810 matched score deltas from 891 score rows;
  there were 0 test-identity mismatches, 0 numerical delta mismatches, and 0
  held-out scenes in corresponding training lists. The review clarified that
  `M1-M0` means `score(M1)−score(M0)` (positive favors M1); source CSV values
  and implementation agree, and no numerical recalculation was needed. The
  formal report's “right/left model” wording is ambiguous and should not be
  copied without this explicit convention.
- **Scope/limitations:** Stage2 selection-conditional only; overlapping windows,
  multiple PRNs and MPCs within scenes are repeated observations. Nine core
  scenes (only three Mountain/Valley) and overlapping LOSO training folds do
  not support path-row p-values or independent-fold confidence intervals.
  Candidate rankings are exploratory among successful fits; failures and
  unsupported records are retained. No alpha pilot, CIR association, MATLAB,
  SAGE, GNSS-SDR, or scientific payload access occurred.

The approved WP3 execution specification remains unchanged at
`docs/superpowers/plans/2026-10-28-mainline-stage2-wp3-environment-geometry-modeling.md`
(SHA-256 at execution `4245ca034114ff982df8e835a6be052e8725f9280bf012ca8169da47785714a1`).
The separately maintained execution record is
`docs/superpowers/plans/2026-10-28-mainline-stage2-wp3-execution-record.md`.
The bounded analysis and independent review are complete with limitations.
Paper-safe findings are candidate-specific, Stage2-selection-conditional and
exploratory across nine core scenes; no independent-fold CI, causal elevation
effect, complete tail pass, or final all-13-scene parameter model is claimed.
**Next WP3 action:** Commander confirms whether to retain the recommended
global M0 working baselines and exploratory-only relative-power M2 boundary;
do not run another WP3 fit in the absence of a concrete new question.

### Task 5 point-in-time sample accompanying WP3 (2026-10-28 22:11 +08)

The separate CIR successor release
`mainline_1023_cir_v1_20261028T120447205Z_task5successor43r1` has request
SHA-256
`1b95146f42a2383f26bbef0bfc1679f9096f3778e67c51fa765af953f04474df` and
audit `RUNNING`. Four new tasks have PASS receipts, plus 37 inherited PASS,
so cumulative accepted count is 41/80 (4/43 new; 39 new tasks remain).
G18/ch9, G23/ch11, G26/ch3 and G05/ch10 are PASS. At the read-only check,
G16/ch9 (`run_20261003_F1023_V70_D0120_P9_G16_ch9`) was current; Coordinator
PID 17124, worker PowerShell PID 23592, MATLAB launcher/worker PIDs 39444 and
31756 were present. The batch scheduled task was Running; the existing
30-minute and hourly monitor tasks reported LastTaskResult 0 (last runs 22:05
and 22:10 +08 respectively). No completion receipt exists. This is only the
2026-10-28 22:11 +08 sample, not a promise of continued progress. WP3 did not
interact with Task 5 or inspect CIR/HDF5 scientific payloads.

**Follow-up at 2026-10-28 22:20:11 +08:** the audit remained `RUNNING`, with
five new PASS (42/80 cumulative; 5/43 new and 38 new tasks remaining). The
current identity advanced to
`run_20261003_F1023_V70_D0120_P9_G18_ch1` (started 22:12:48 +08). Coordinator
PID 17124, worker PID 29820, MATLAB launcher PID 34664 and MATLAB worker PID
9748 remained present; MATLAB worker CPU time was 213 seconds. The coordinator
scheduled task was Running; the 30-minute monitor was Ready (last result 0,
next 22:35) and the hourly monitor Ready (last result 0, next 23:10). This
read-only follow-up supersedes the 22:11 operational sample only; it is not a
completion claim.

**Follow-up sample at 2026-10-28 23:30:40 +08:** the same release audit was
`RUNNING` with seven new PASS plus 37 inherited (44/80 total); current identity
was `run_20261003_F1023_V70_D0120_P9_G26_ch6`, started 23:01:45 +08. Coordinator
PID 17124, worker PowerShell PID 20688, and MATLAB launcher/worker PIDs 8812
and 21660 were present. The batch scheduled task was Running (LastTaskResult
267009); the 30-minute monitor was Ready, last result 0 at 23:05 and next
23:35; hourly monitor Ready, last result 0 at 23:10 and next 00:10. This
sample did not inspect CPU/file progress or new System storage events; it is a
process/audit/task snapshot only. No production process or artifact was
modified.
