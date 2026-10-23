# Mainline 10.23 MHz Stage2 Model Preparation Design

**Status:** preparation design only; no formal fit, Gate F, or model validation is claimed.

## Intent

Prepare a new Mainline Stage2 model from the accepted all-MPC ledger while Task 5 CIR production continues independently. The work defines the selected population, observation hierarchy, candidate marginal families, scene-held-out validation, and an exact future CIR/PDP association contract. It adds only small pure-Python utilities and synthetic tests. Formal fitting waits for Task 5/Gate E and the complete Task6/Gate F association audit.

## Governing sources and current evidence

- The population policy follows the Mainline audit/CIR/Stage2 plan at docs/superpowers/plans/2026-10-22-mainline-1023-audit-cir-stage2-model.md, especially its Task 6 and Task 7 sections.
- The prior candidate-family and validation choices come from docs/ACADEMIC_CHANNEL_MODELING_MASTER_PLAN.md and the QA-passed Stage3 model configuration/report. They are candidate references only; Stage3 parameters and conclusions are not transferred to the different Stage2 population.
- The accepted Stage2 ledger disposition is STAGE2_LEDGER_PASS_CIR_ASSOCIATION_PENDING, not Gate F. The ledger is tied to cohort SHA-256 287e891fae0cd294a85c073080611a19b7389ece46240b89cb1d5dab4df90229 and preserves 16,761 unique run/window/path rows: 7,847 direct/reference and 8,914 MPC candidates. The Task6 summary reports 2,228 Stage3-persistent MPC, 120 Stage4-confirmed MPC, 1,587 Stage4-unmapped MPC, four Stage4-only path rows, and nine missing elevation classifications. These later-stage labels do not select the modeling population.
- Scene/environment coverage was summed from the small Gate A audit CSV `E:/GNSS_Multipath_Project/reports/data_consolidation_20261003/mainline_1023_model_v1/audit_20261022T074307Z/task_audit.csv` (SHA-256 `0689082db444486211fe5b4e3a1f9a0be00da697dea145f5ee0e4b5547327825`); the committed Task6 summary is `reports/data_consolidation_20261003/mainline_1023_model_v1/task6_stage2_task_summary_20261023.csv` (SHA-256 `524305c3d108eef3df52a39f09eaf395b37725de0898248648ce781da91a4dbb`). No raw IQ, MAT, HDF5, CIR payload, MATLAB, or SAGE execution is needed for this preparation.

## Approaches considered

1. Reuse the frozen Stage3 model and its fitted parameters directly. Rejected because its population is Stage3 reliable/persistent observations, not all Mainline Stage2 MPCs.
2. Fit the new Stage2 population immediately or read CIR/HDF5 now. Rejected because Task5 is incomplete and Gate F is pending; this would cross the user's data and execution boundary.
3. Prepare a Stage2-specific specification, scene/window support summaries, scene-blocked split utility, and exact-key CIR association helper with synthetic tests. Selected because it prepares the next gate without fitting or competing with CIR production.

## Selection frame and estimand

The 83 eligible tasks contain 285,752 Stage0 valid 40-ms windows. Stage1 screens windows; Stage2 evaluates selected windows and emits selected path rows. The audit reports 7,847 Stage2-evaluated windows, or 2.75% of Stage0 valid windows, and 16,761 selected path rows. The equal totals of Stage2 windows and direct/reference rows are consistent with one path-1 reference row per evaluated window. Of the Stage2 path rows, 8,914 are MPC candidates.

This is a selected population. The path-level estimand is the distribution of Stage2 MPC path-observations conditional on inclusion by the existing Stage1/Stage2 pipeline and membership in the frozen 83-task cohort. It is not an unconditional physical multipath distribution over all Stage0 windows, and it is not a physical-reflector census. Stage3 persistence and Stage4 confirmation/unmapped status remain annotations. Direct paths are retained for reference and are not MPC candidates.

For a window-level count view, derive MPC count only for the 7,847 Stage2-evaluated windows represented in Stage2. A selected window with a direct/reference row and no MPC rows can have count zero within this selected-window frame. A Stage0 window not represented in Stage2 is not added as a zero-count observation. No unconditional occurrence probability is estimated from this denominator.

### Scene and environment coverage

Coverage below is computed by summing the Gate A per-task audit; the percentage is Stage2-evaluated windows divided by Stage0-valid windows, not a detection rate.

| Environment | Scenes | Runs/tasks | Stage0 windows | Stage2-evaluated windows | Stage2 coverage | All Stage2 paths | MPC candidates |
|---|---:|---:|---:|---:|---:|---:|---:|
| Highway/Open | 2 | 18 | 182,802 | 1,290 | 0.71% | 1,865 | 575 |
| Mountain/Valley | 3 | 20 | 20,478 | 1,974 | 9.64% | 4,611 | 2,637 |
| Special Reflective | 2 | 16 | 38,076 | 1,656 | 4.35% | 3,660 | 2,004 |
| Urban | 6 | 29 | 44,396 | 2,927 | 6.59% | 6,625 | 3,698 |
| Total | 13 | 83 | 285,752 | 7,847 | 2.75% | 16,761 | 8,914 |

Selection coverage differs substantially by environment, especially for the long Highway/Open scene. Therefore pooled Stage2 distributions must be described as conditional on the Stage2 selection process. Do not compare environment counts as if they were equal-exposure occurrence rates.

The per-scene coverage breakdown is below. Counts are summed over the included
PRN/channel runs in each scene; the percent denominator remains that scene's
Stage0-valid windows. It is not a per-path detection probability.

| Scene ID | Environment | Runs | Stage0-valid windows | Stage2-evaluated windows | Coverage | MPC candidates |
|---|---|---:|---:|---:|---:|---:|
| F1023_V120_D0121_P2 | Highway/Open | 13 | 177,588 | 841 | 0.47% | 104 |
| F1023_v50_D0127_P1 | Urban | 5 | 9,090 | 386 | 4.25% | 115 |
| F1023_V70_D0117_P2 | Mountain/Valley | 7 | 7,092 | 592 | 8.35% | 837 |
| F1023_V70_D0117_P4 | Mountain/Valley | 7 | 6,250 | 761 | 12.18% | 1,093 |
| F1023_V70_D0120_P1 | Urban | 3 | 6,327 | 330 | 5.22% | 334 |
| F1023_V70_D0120_P5 | Urban | 5 | 4,242 | 483 | 11.39% | 671 |
| F1023_V70_D0120_P7 | Urban | 4 | 8,916 | 439 | 4.92% | 707 |
| F1023_V70_D0120_P8 | Urban | 4 | 3,540 | 447 | 12.63% | 442 |
| F1023_V70_D0120_P9 | Special Reflective | 9 | 19,909 | 987 | 4.96% | 1,172 |
| F1023_V70_D0122_P1 | Urban | 8 | 12,281 | 842 | 6.86% | 1,429 |
| F1023_V70_D0122_P2 | Special Reflective | 7 | 18,167 | 669 | 3.68% | 832 |
| F1023_V80_D0117_P8 | Highway/Open | 5 | 5,214 | 449 | 8.61% | 471 |
| F1023_v90_D0117_P7 | Mountain/Valley | 6 | 7,136 | 621 | 8.70% | 707 |

### Elevation support

Only categorical High/Mid/Low group labels are available; numeric mean elevation is missing for all 83 tasks and must remain unavailable. The nine missing classifications remain MISSING.

| Population/group | Scenes | Runs/tasks | MPC candidates |
|---|---:|---:|---:|
| All High | 13 | 20 | 2,797 |
| All Mid | 13 | 33 | 4,435 |
| All Low | 11 | 21 | 1,275 |
| All MISSING | 4 | 9 | 407 |
| Urban High | 6 | 10 | 1,467 |
| Urban Mid | 6 | 14 | 2,072 |
| Urban Low | 4 | 5 | 159 |

Urban has six scenes overall, but the Urban-Low subset has only four scenes/five runs and 159 MPC rows. Elevation-group results are therefore support-limited and scene-level uncertainty must be reported. Continuous-elevation inference is out of scope because no numeric elevation values are present.

## Analysis hierarchy and leakage control

- Path-level: positive excess delay relative to the direct/reference path; signed Doppler offset relative to the direct/reference path; relative power in dB. These are algorithm-produced Stage2 path-observations, not physical reflector identities or absolute received power.
- Stage2 window-level: count and descriptive summaries of MPC rows among Stage2-evaluated windows only. Overlapping windows are repeated observations.
- Run-level: PRN/channel-specific SAGE task identified by run_id. Windows and paths within a run are clustered/repeated.
- Scene-level: scene_id is the independent holdout unit. All runs, PRNs/channels, and overlapping windows from a held-out scene stay together. Random path/window splits are prohibited.

Global and Urban leave-one-scene-out (LOSO) folds are the primary generalization design. Report each held-out scene, its training/test support, and per-scene scores before any aggregate. Use scene-block bootstrap intervals and a run-level sensitivity view; do not use the 8,914 path rows as independent scene replicates. If a stratum/fold lacks training or held-out support, report the affected result as unavailable/descriptive rather than silently pooling or imputing it. Other environments are descriptive or cautious external comparisons because they have only two or three scenes each.

## Candidate marginals and evaluation contract

Reuse the master plan's Phase-1 canonical marginal families as the Stage2
reference candidates: Lognormal excess delay, Normal signed relative Doppler,
and Normal relative power. The previously QA-passed Stage3 configuration's
Gamma/Weibull delay and Laplace/Student-t Doppler and power families are
bounded alternatives for a later comparison, not transferred fit results or
parameters. These empirical families describe Stage2-selected observations;
they do not assert a propagation mechanism.

| Quantity | Interpretation and support | Candidate families | Estimation and comparison |
|---|---|---|---|
| Excess delay (samples; chips may be reported secondarily) | Nonnegative delay relative to the direct/reference path; positive support and right-skew are plausible | Reference: Lognormal; alternatives: Gamma, Weibull | Later: maximum likelihood using training scenes only; grouped-LOSO held-out log likelihood is primary; AICc/BIC are within-training complexity summaries; compare empirical CDF and reported quantiles |
| Signed Doppler offset (Hz) | Relative frequency offset against the direct/reference path; it is not scatterer velocity | Reference: Normal; alternatives: Laplace, Student-t | Later: maximum likelihood using training scenes only; grouped-LOSO held-out log likelihood; AICc/BIC; empirical CDF/quantiles and scene-block intervals |
| Relative power (dB) | Stage2 relative-power measure; not calibrated absolute receive power | Reference: Normal; alternatives: Laplace, Student-t | Later: maximum likelihood using training scenes only; grouped-LOSO held-out log likelihood; AICc/BIC; empirical CDF/quantiles and scene-block intervals |

The global Stage2 baseline is evaluated first. An Urban subset model follows. Urban High/Mid/Low analyses are separate support-gated strata, not continuous-elevation fits. The existing master-plan hierarchy Global → Environment → Environment×Elevation is a reference for partial sharing only if later support justifies it; this preparation does not create a new pooling model or fit. A Gaussian copula is an existing Phase-1 dependence reference only at global/environment or otherwise support-gated levels; it is not fit now. No parametric window-count family is selected now: counts are descriptive until selection/exposure support and Gate F are reviewed. The Master Plan's conditional MDN/normalizing-flow Phase 2 remains `PLANNED_ONLY` and unauthorized; no such model is implemented or trained here. Ricean-K and absolute-power models are out of scope.

## CIR/PDP association contract

The Stage2 path ledger remains keyed by (run_id, window_id, path_id). Its window_id values are positive canonical decimal IDs; reject noncanonical aliases such as `01` rather than splitting or coalescing their counts silently. CIR/PDP features are window-level and use the exact pair (run_id, window_id); window_id alone can collide across runs. Preserve a separate CIR-window feature table and link it to every Stage2 path row by the exact pair. Do not treat replicated window features as independent per-path measurements.

Every Stage2 row is retained and receives one explicit state:

| State | Meaning |
|---|---|
| UNASSOCIATED | Task5 receipt/HDF5 read-back for that run is incomplete or not validated; no absence claim is made |
| NO_CIR_CORRESPONDENCE | The exact pair is absent from a run whose task receipt and complete Stage0↔PDP window index both passed; retain the Stage2 row and expose the coverage mismatch |
| ASSOCIATED_VALIDATED | Exact run_id/window_id exists in the validated Stage0/PDP index for a PASS Task5 run |

A validated index must bind the expected run_id to the task-receipt run_id and HDF5 run_id, require PASS receipt and HDF5 read-back, and have an exact complete Stage0 window_id ↔ PDP window_id sequence/count. Window IDs must be positive canonical decimal values. A claimed PASS with mismatched identity, aliases/duplicates, or an incomplete sequence fails closed. A failed or incomplete run remains UNASSOCIATED; it cannot manufacture NO_CIR_CORRESPONDENCE. Task5 production failures remain visible and cannot be repaired by this helper. No CIR payload is read in Task7 preparation.

## Non-goals and gates

- No formal parameter estimation, significance testing, model selection result, Gate F, Gate G, or scientific model-validation claim.
- No CIR export, HDF5 read-back, complex-alpha extraction, MATLAB/SAGE execution, raw-IQ read, or change to Task5 code, release, worker, monitor, or outputs.
- No change to Manifest/Summary, Stage2 source, frozen algorithms, old Phase-1/r3 artifacts, Task6 ledger, prior CIR pilots, or excluded tasks.
- Full CIR feature association waits for Task5 completion and independent Gate E/F validation. Formal model fitting follows only after that gate.

## Implementation choice

Add a pure-stdlib Python preparation module with three tested behaviors: derive MPC counts only for represented Stage2 windows, build scene-level LOSO folds without scene leakage, and attach the three CIR association states without dropping or changing Stage2 rows. The helper consumes validated window-index evidence; it does not read HDF5. Add a synthetic-only test module. No production fitter or large-data command is introduced.
