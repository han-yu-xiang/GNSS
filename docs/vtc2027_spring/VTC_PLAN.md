# VTC2027-Spring Regular Paper Plan

## 1. Submission target

This plan targets a five-page VTC2027-Spring Regular Paper submission due 2026-09-01. The internal complete-draft target is 2026-08-31. The primary positioning is Antenna Systems, Propagation, and RF Design, with secondary relevance to positioning/localization/navigation and signal processing for wireless communications.

## 2. Working title

**Primary:** *SAGE-Based High-Resolution Multipath Characterization of GPS L1 C/A Signals in Dynamic Vehicular Environments*

**Alternative:** *Measurement-Based Characterization of Dynamic GNSS Multipath Using High-Resolution SAGE Path Extraction*

## 3. Scientific question

> Can high-resolution and physically consistent multipath components be extracted and confirmed from real dynamic GPS L1 C/A raw-IQ measurements using a NAV-aided hierarchical SAGE processing framework, and what path-level propagation characteristics are observed across realistic environments and satellite geometries?

This is a measurement and path-characterization question. It is not a claim that the paper invents SAGE or solves positioning/mitigation.

## 4. Frozen VTC contributions

1. **Measurement chain and dataset.** A real dynamic GPS L1 C/A raw-IQ measurement chain is organized across realistic propagation environments. The documented setup includes TEST-TREE RF-Catcher V2, interleaved little-endian int16 IQ, a roof-mounted RHCP GNSS dome antenna, a moving vehicle platform, and 10.23 MHz production scenes covering Urban, Mountain/Valley, Highway/Open, and Special Reflective metadata classes.
2. **NAV-aided hierarchical extraction.** Stage0 builds valid NAV-symbol and 40 ms windows; Stage1 screens correlation candidates; Stage2 evaluates fractional SAGE model orders L=1–4; Stage3 checks temporal persistence; Stage4 performs 100 ms multi-snapshot joint confirmation. `L>=2` is not a confirmed multipath label, and a Stage3 reliable center is not a confirmed event. Only the current Stage4 criterion admits a confirmed event/path.
3. **Measurement-based path characterization.** Confirmed paths are characterized by available excess delay, relative Doppler, relative power, and, when supported by the artifact, persistence/lifetime and elevation/environment context. The VTC paper will use empirical observations and bounded comparisons, not claim a completed parametric channel model.

## 5. Explicit non-goals

The VTC paper does not claim:

- a new SAGE estimator;
- positioning accuracy improvement or a multipath mitigation algorithm;
- a complete PDP/RMS-delay-spread/Doppler-spread/K-factor statistical model;
- a synthetic GNSS channel generator;
- a complete coverage-complete path/event database;
- that all 19 scenes or all 10.23 MHz production tasks have been processed.

The raw-coarse/sampling/v3 work is a computational acceleration investigation. Its posterior event-preservation failure is retained as a negative result and limitation, not as a production method.

## 6. Current evidence baseline

| Evidence item | Current status | Paper use |
|---|---|---|
| Reference scene `F1023_V70_D0117_P2`, seven PRNs | Completed / Validated | Hierarchical behavior and control/confirmed cases |
| Wave-A G16/G25/G12 (distinct from formal A3 G16) | Completed / Validated | Cross-task execution-chain validation |
| Formal A1 `F1023_V70_D0117_P4/G11/ch2` | Completed / QA PASS; 3 confirmed events and 3 paths | Formal production example |
| Formal A2 `F1023_V70_D0120_P1/G18/ch2` | Completed / QA PASS; zero confirmed events under the criterion | Valid zero-event pipeline case |
| Formal A3 `F1023_V70_D0120_P5/G16/ch1` | Scientific artifact QA PASS; execution-policy caveat retained | Pipeline validation case, not Batch A release evidence |
| Controlled G12 `F1023_V70_D0117_P4/G12/ch4` | Completed / QA PASS / Available; 3 confirmed events and 3 paths | Available evidence; core Results inclusion remains pending |
| Full 10.23 MHz production | In progress | Future evidence source |

The current G12 status is taken from the actual execution directory `dataset_generation_logs/batch_sage_execution/batch_sage_execution_20260814T024904Z/` and independent QA report `docs/10MHz_FULL_SAGE_PRODUCTION_CONTRACT_ACCEPTANCE_G12_QA_REPORT.md`. Its status history records executor completion with exit code 0; the task log reports 21 output files, Stage0 `895` valid NAV symbols and `893` windows, Stage1 `99` candidates, Stage2 final L1/L2/L3/L4 counts of `30/7/7/55`, Stage3 `15` reliable centers, Stage4 `8` joint results, and independent QA confirms `3` confirmed events and `3` paths. G12 is `Completed / QA PASS / Available evidence`; it is not automatically inserted into the VTC core Results section.

### 6.1 Evidence-Priority Production Strategy

Batch A continuous production is released, but VTC submission does not wait for all 67 production-manifest tasks. The current strategy is to run a small, evidence-complementary wave, perform independent QA, update the evidence matrix, and then decide whether more SAGE production is needed. The formal queue is `docs/vtc2027_spring/VTC_PRODUCTION_PRIORITY_QUEUE.md`.

The read-only queue audit reviewed the 48 Batch A rows against the current production summary, metadata, input provenance, geometry summaries and output namespaces. Four target namespaces already exist (A1 G11, controlled G12, A2 G18 and protected historical A3 G16), leaving 44 new-only planning candidates. The proposed first wave is one task per scene from Special Reflective, Highway/Open and Mountain/Valley; it is not a prediction of confirmed events and does not authorize execution.

The stop decision is evidence-based rather than count-based: after QA, stop when the four environment classes have usable evidence or the paper claim is explicitly narrowed, LOW/MID/HIGH denominators are geometry-QA-complete, and the existing confirmed/rejection/zero-event cases plus planned figures are adequately supported. Completion of all 67 tasks, a complete statistical model, equal environment sample counts and 20.46 MHz are not VTC prerequisites.

## 7. VTC Results plan

### Result A — Hierarchical filtering

Show the reduction from the complete Stage0 window mother set through Stage1 candidates, Stage2 model-order evaluation, Stage3 reliable centers, and Stage4 confirmed events. The figure/table must preserve the distinction between evidence stages and confirmed labels.

### Result B — Representative confirmed path case

Use an existing confirmed reference-scene or A1 Stage4 case to show direct/secondary path parameters and the Stage4 confirmation context. Exact window/path values must be extracted from the frozen Stage4 CSV/MAT artifact before final drafting.

### Result C — Path-level characterization

If the completed production evidence supports it, report empirical distributions or scatter plots for excess delay, relative power, and relative Doppler. Do not call the result a fitted channel model unless a separately validated analysis supports that claim.

### Result D — Bounded geometry/environment observations

Use LOW/MID/HIGH elevation definitions and the available Urban/Mountain/Valley/Highway/Open/Special Reflective metadata only where window-level geometry alignment and sample denominators are QA-complete. Avoid high-dimensional or underpowered claims.

## 8. Submission timeline

| Date | Planned work | Gate/status |
|---|---|---|
| Aug 14–15 | Lock scope, workspace, evidence matrix; record G12 execution and independent-QA status | Completed for G12; core-results selection pending |
| Aug 15–20 | If production is released after QA, prioritize VTC evidence and compress Sections I–III | Planned |
| Aug 18–23 | Select a representative confirmed case and produce first aggregate/figure drafts | Planned |
| Aug 22–26 | Iterate Results text/figures and complete claim-to-evidence mapping | Planned |
| Aug 25–28 | Complete English five-page draft and references | Planned |
| Aug 28–30 | Page compression, figure readability, language and IEEE/VTC consistency QA | Planned |
| Aug 31 | Internal submission-ready package | Planned |
| Sep 1 | External submission deadline | Planned |

Dates are planning targets, not evidence that the corresponding work is complete.

## 9. Submission gates

1. **Production infrastructure accepted:** normal-user Windows execution, immutable request, `new_only`, and independent QA remain valid.
2. **Representative evidence coverage sufficient:** the evidence matrix has at least one confirmed case, one valid zero-event/control case, one rejection/control case, and cross-task validation.
3. **Confirmed path aggregation ready:** path-level rows and provenance are extracted without calling Stage2/Stage3 outputs confirmed.
4. **Core figures ready:** pipeline/funnel, representative path case, and bounded characterization figures have traceable sources.
5. **Complete five-page draft:** all claims have evidence or are explicitly marked as planned/limitation.
6. **Scientific consistency QA:** stage semantics, zero-event wording, G16 contract caveat, geometry limitation, and v3 negative result are consistent.
7. **Venue-format QA:** IEEE/VTC template, page count, references, figure labels, and submission package pass review.

## 10. Safety and status rules

- Do not modify the production manifest, immutable requests, SAGE outputs, reference results, or historical raw-coarse artifacts for paper drafting.
- Do not promote G12 into a core VTC Results claim without evidence-matrix review; its QA-passed output is available evidence, not a completed statistical conclusion.
- Do not treat G16 as Batch A release evidence.
- Do not use `L>=2`, Stage3 reliable centers, or unconfirmed candidates as confirmed multipath.
- Do not state that the statistical model, event database, or all scenes are complete.
- Do not read raw IQ or run MATLAB/SAGE as part of paper workspace maintenance.

## 11. Submission/template setup status

- Official VTC CFP and public TrackChair requirements were audited on 2026-08-14.
- The current official rules are: five-page original/unpublished full paper; up to seven pages with charges; no more than eight pages for review; regular-paper deadline 2026-09-01; acceptance notification 2026-12-20.
- The public VTC pages do not expose a VTC-specific LaTeX class. The manuscript therefore uses `\documentclass[conference]{IEEEtran}` as the generic IEEE conference target.
- `manuscript/latex/main.tex`, `references.bib`, `submission/SUBMISSION_REQUIREMENTS.md`, and `submission/PAGE_BUDGET.md` are implemented.
- The local machine has no TeX compiler and no `IEEEtran.cls`. Two read-only attempts to retrieve the official IEEE package returned zero-byte responses; the original template has not been fabricated or silently substituted.
- Figure 1 has an editable TikZ source and an SVG draft. A rendered PDF remains pending an approved local LaTeX/graphics toolchain.

## 12. Author-approved conditional-model revision route (2026-08-31)

The author approved a revised VTC route limited to Urban and Mountain/Valley measurements and three elevation ranges. The revised model uses 518 persistent path observations, of which 487 have valid elevation assignments. These observations are not called Stage4-confirmed paths in the paper.

The admitted paper-facing statistical result is a track-weighted three-dimensional GMM for excess delay, absolute relative Doppler and relative power, evaluated by leave-one-scene-out validation. The manuscript directly compares weighted measured histograms with fitted marginal PDFs and does not expose internal pooling hyperparameters or support-status labels. Those implementation and QA details remain unchanged in the model evidence. The model is conditional on an observation having passed temporal-consistency retention; it is not a multipath-occurrence model or a complete stochastic channel model.

The current bilingual manuscript integration is isolated under `supplemental_data_outputs/urban_mountain_stage3_elevation_model_review_v3_conditional_gmm/manuscript/`. The historical canonical manuscript under `manuscript/latex/` remains unchanged until a separate author replacement decision.
