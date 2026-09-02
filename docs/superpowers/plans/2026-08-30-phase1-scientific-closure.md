# Phase-1 Traditional Channel Modeling Scientific Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the frozen canonical Stage3 Environment×Elevation model `environment_elevation_stage3_path_model_v1_20260829_r3` into an auditable Phase‑1 scientific closure for journal and master's-thesis use, without rebuilding the model or starting Phase‑2 AI work.

**Architecture:** A new read-only analysis builder consumes only the canonical r3 CSV/JSON artifacts and emits effect, characterization, robustness, support-gap, and publication-source tables into a new-only closure namespace. A separate auditor re-reads those outputs, recomputes the key contrasts and provenance gates independently, and writes the final QA result; the two authoritative Markdown documents summarize the same machine-readable conclusions.

**Tech Stack:** Python 3.12, NumPy/SciPy from `D:\Research\ChannelModeling-Agent\.venv`, standard-library CSV/JSON/hashlib, pytest, Markdown, and optional Matplotlib plotting-data generation only. No MATLAB, SAGE, raw IQ, 20.46 MHz, or new production request.

**Spec:** `C:\Users\Jing_\.codex\attachments\bda01d4c-ece5-4c7c-b674-87c596ef2f96\pasted-text.txt`

## Global Constraints

- Canonical traditional model: `environment_elevation_stage3_path_model_v1_20260829_r3`; do not rebuild or modify r3, r1, or r2.
- Primary population: 783 academic Stage3 observations, 445 centers, 366 algorithm-level tracks, 716 elevation-ready observations, 50 runs, 12 scenes, 18 PRNs.
- Primary statistical unit: `WEIGHTED_OBSERVATION`; weight is `1 / algorithm_track_size`; all inference is scene/run clustered.
- Primary uncertainty is the existing scene-block bootstrap; run-block and algorithm-track-median views are sensitivity analyses.
- Stage4 is `HIGH_CONFIDENCE_VALIDATION_ONLY`, never a Stage3 selection or tuning source; Ricean K remains `NOT_IDENTIFIABLE`.
- Formal elevation interface remains `LOW=[0,30)`, `MID=[30,60)`, `HIGH=[60,90]`; `Highway/Open–LOW` remains `NO_DIRECT_SUPPORT` without synthetic fill.
- Use grouped held-out/LOSO evidence and weighted effect sizes; never treat 783 rows as independent observations and do not use p-value-only conclusions.
- All closure artifacts are new-only under `dataset_generation_logs/channel_modeling/phase1_scientific_closure_20260830_r1/`; never overwrite r3/r1/r2 or historical QA.
- Do not invoke MATLAB/SAGE/batch, read raw IQ, process 20.46 MHz, train AI, create production requests, modify Stage4, or touch darkroom branches.
- Existing Engineering/Paper handoffs are already dirty; preserve unrelated user changes. Update only the Paper Handoff if the new scientific facts require synchronization; do not create a parallel handoff.

---

### Task 1: Create the Master Plan and freeze the closure inputs

**Files:**
- Create: `docs/ACADEMIC_CHANNEL_MODELING_MASTER_PLAN.md`
- Create: `docs/superpowers/plans/2026-08-30-phase1-scientific-closure.md`
- Read: `dataset_generation_logs/channel_modeling/environment_elevation_stage3_path_model_v1_20260829_r3/model_manifest.json`
- Read: `dataset_generation_logs/channel_modeling/environment_elevation_stage3_path_model_v1_20260829_r3/independent_qa_result.json`

**Interfaces:**
- Consumes: canonical r3 manifest, receipt, independent QA result, and report.
- Produces: a master plan that names Phase 1 as traditional modeling + scientific closure, Phase 2 as AI conditional generative modeling, and records Phase 2 as planned-only and unauthorized.

- [ ] Write the master plan with the canonical r3 identity, population contract, protection rules, Phase‑1 closure task list, provisional Phase‑2 goal/models/evaluation, and the explicit Phase‑2 GO/NO-GO condition.
- [ ] Record that this closure is active and that no new traditional model is being created.
- [ ] Verify the plan contains `PHASE_1_MODEL_BUILD = COMPLETE`, `PHASE_1_SCIENTIFIC_CLOSURE = ACTIVE`, `PHASE_2 = PLANNED_ONLY`, and `PHASE_2_EXECUTION_AUTHORIZED = NO`.

### Task 2: Define the effect, contrast, and publication-data interfaces test-first

**Files:**
- Create: `scripts/analysis/channel_modeling/tests/test_phase1_scientific_closure.py`
- Create: `scripts/analysis/channel_modeling/build_phase1_scientific_closure.py`

**Interfaces:**
- Consumes: r3 summary/model/bootstrap/sensitivity CSVs.
- Produces: `phase1_effect_table.csv`, `environment_characterization.csv`, `elevation_characterization.csv`, `environment_elevation_interaction.csv`, and `robustness_matrix.csv` with stable columns and deterministic ordering.

- [ ] Write failing pure-function tests for weighted contrasts, interval overlap/effect interpretation, LOSO stability labels, support-strength labels, scope/cell ordering, and exact final decision labels.
- [ ] Run the focused tests and record the expected missing-import failure.
- [ ] Implement pure functions that calculate weighted median/quantile contrasts from the existing summary tables, compare model quantiles and bootstrap intervals, and label `ROBUST`, `MOSTLY_ROBUST`, `SENSITIVE`, or `INCONCLUSIVE` without row-wise independence.
- [ ] Include the required effect-table fields: `parameter`, `comparison`, `effect_direction`, `effect_size`, `bootstrap_interval`, `LOSO_stability`, `support_strength`, `scientific_interpretation`.
- [ ] Include separate environment, elevation, interaction, and robustness outputs for delay, signed Doppler, and relative power.
- [ ] Re-run the focused tests and require green results.

### Task 3: Build Tasks A–D scientific effects and environment/elevation characterization

**Files:**
- Modify: `scripts/analysis/channel_modeling/build_phase1_scientific_closure.py`
- Create: `dataset_generation_logs/channel_modeling/phase1_scientific_closure_20260830_r1/`

**Interfaces:**
- Consumes: r3 `weighted_parameter_summary.csv`, `selected_marginal_models.csv`, `candidate_family_scores.csv`, `scene_block_bootstrap.csv`, `run_block_sensitivity.csv`, and `continuous_elevation_diagnostics.csv`.
- Produces: machine-readable effects and per-environment/per-elevation characterization with bounded scientific wording.

- [ ] Compute environment contrasts against the weighted global model and pairwise environment contrasts using model-derived q050/IQR/quantiles, with scene-block intervals where available.
- [ ] Compute LOW/MID/HIGH contrasts separately for each parameter, preserving the empty `Highway/Open–LOW` cell as `NO_DIRECT_SUPPORT`.
- [ ] Compute environment×elevation interaction evidence from cell-versus-environment parent differences and bootstrap/LOSO support, not visual differences alone.
- [ ] Record per-environment delay/Doppler/power behavior, joint dependence source/status, derived-statistic references, elevation evidence, uncertainty, and limitations; use `NO_ROBUST_DIFFERENCE` where separation is not supported.
- [ ] Record candidate family and grouped LOSO evidence without treating cell-local family variation as a universal physical law.
- [ ] Record formal labels `SUPPORTED`, `PARTIAL`, `INCONCLUSIVE`, or `NOT_SUPPORTED` for each elevation effect and interaction parameter.

### Task 4: Build Tasks E–H channel statistics, Stage4 selection, continuous elevation, and dependence interpretation

**Files:**
- Modify: `scripts/analysis/channel_modeling/build_phase1_scientific_closure.py`
- Create: `dataset_generation_logs/channel_modeling/phase1_scientific_closure_20260830_r1/stage4_selection_analysis.csv`
- Create: `dataset_generation_logs/channel_modeling/phase1_scientific_closure_20260830_r1/joint_dependence_interpretation.csv`

**Interfaces:**
- Consumes: r3 `derived_channel_statistics.csv`, `persistence_duration_statistics.csv`, `joint_dependence_models.csv`, `stage3_stage4_sensitivity.csv`, `stage3_stage4_cdf_comparison.csv`, and `continuous_elevation_diagnostics.csv`.
- Produces: channel-level support decisions, bounded Stage4 selection-effect analysis, continuous-elevation evidence labels, and AI-joint-density motivation.

- [ ] Separate path-level fitted parameters from center/channel-level derived statistics; preserve conditional RMS and relative-power caveats and do not compute K.
- [ ] Quantify Stage4-vs-Stage3 differences in delay, Doppler, power, persistence, environment, and elevation using available denominators and explicitly state Stage4 is not external truth.
- [ ] Test whether Stage4 differences are consistent with stronger-path, shorter-delay, Doppler-range, persistence, environment, or elevation selection; report only observed directions.
- [ ] Label each environment×parameter continuous-elevation result `ROBUST`, `WEAK`, `INCONSISTENT`, or `INSUFFICIENT`; return `RECOMMENDED`, `CONDITIONAL`, or `NOT_RECOMMENDED` for Phase 2.
- [ ] Interpret copula pairwise correlations, environment variation, cell support, and future AI motivation without estimating unsupported covariance structures.

### Task 5: Build Tasks I–K robustness, data-gap, and paper-ready source plan

**Files:**
- Modify: `scripts/analysis/channel_modeling/build_phase1_scientific_closure.py`
- Create: `dataset_generation_logs/channel_modeling/phase1_scientific_closure_20260830_r1/robustness_matrix.csv`
- Create: `dataset_generation_logs/channel_modeling/phase1_scientific_closure_20260830_r1/support_gap_decision.csv`
- Create: `dataset_generation_logs/channel_modeling/phase1_scientific_closure_20260830_r1/figure_table_plan.csv`
- Create: `dataset_generation_logs/channel_modeling/phase1_scientific_closure_20260830_r1/publication_table_sources.csv`
- Create: `scripts/analysis/channel_modeling/plot_phase1_scientific_closure.py`

**Interfaces:**
- Consumes: all prior closure tables and r3 source tables.
- Produces: a final scientific robustness matrix, separate decisions for bounded claims/12-cell completeness/continuous elevation/future AI, and ranked CORE/SUPPLEMENTARY/THESIS_ONLY figure/table source records.

- [ ] Compare weighted, raw clustered, algorithm-track median, Stage4, scene bootstrap, run sensitivity, and LOSO for every principal conclusion.
- [ ] Classify every one of the 12 cells with current support status and separately assess Highway/Open–LOW and all sparse/prior-dominant cells.
- [ ] Return independent data requirements for current bounded journal claims, complete 12-cell modeling, continuous-elevation generalization, and future AI.
- [ ] Rank publication figures using the project/VTC boundary: workflow, support matrix, descriptive distributions, channel statistics, dependence, Stage4 sensitivity, and continuous trends; mark fitted stochastic figures as journal/thesis evidence rather than automatic VTC content.
- [ ] Provide minimal table recommendations and machine-readable long-form plotting data; plotting script must read the closure namespace and never raw IQ or SAGE artifacts.
- [ ] Add tests for deterministic ordering, empty-cell handling, and no synthetic fill.

### Task 6: Write the Phase‑1 scientific closure report and update the master plan

**Files:**
- Create: `docs/PHASE1_TRADITIONAL_CHANNEL_MODELING_SCIENTIFIC_CLOSURE.md`
- Modify: `docs/ACADEMIC_CHANNEL_MODELING_MASTER_PLAN.md`
- Conditionally modify: `docs/GNSS_SAGE_PAPER_HANDOFF_CURRENT.md` only by appending verified paper-usable scientific facts and artifact links.

**Interfaces:**
- Consumes: closure namespace, model manifest/receipt, independent QA result, and VTC evidence constraints.
- Produces: plain-language answers to the 12 scientific questions, the exact Phase‑1 completion gate, and a master-plan record that Phase 2 remains planned-only.

- [ ] Write the report with sections for supported trends, environment, elevation, interaction, path distributions, channel statistics, dependence, robustness, Stage4 selection, limitations, 10.23 MHz sufficiency, forbidden claims, and publication figure/table plan.
- [ ] Include exact controlled-value final blocks from the Commander specification.
- [ ] State that `RICEAN_K = NOT_IDENTIFIABLE`, persistence is algorithm-observed, Stage4 is a selection-sensitive validation subset, and no physical reflector identity is inferred.
- [ ] Keep VTC claims bounded to its frozen path-characterization scope; do not edit the VTC manuscript or evidence matrix in this task.
- [ ] Update the master plan with actual closure status and leave Phase 2 `PLANNED_ONLY`.

### Task 7: Implement independent QA and complete the gate

**Files:**
- Create: `scripts/analysis/channel_modeling/tests/test_audit_phase1_scientific_closure.py`
- Create: `scripts/analysis/channel_modeling/audit_phase1_scientific_closure.py`
- Create: `dataset_generation_logs/channel_modeling/phase1_scientific_closure_20260830_r1/independent_qa_result.json`
- Create: `dataset_generation_logs/channel_modeling/phase1_scientific_closure_20260830_r1/independent_qa_report.md`

**Interfaces:**
- Consumes: closure tables, canonical r3 manifest/receipt/QA, and frozen production/source hashes.
- Produces: an independent PASS/FAIL decision and evidence-bound final decision block.

- [ ] Write failing tests for effect-table schema, 12-cell coverage, exact empty-cell preservation, deterministic row counts, frozen r3 identity, and report decision consistency.
- [ ] Run the focused auditor tests to verify the red state.
- [ ] Implement the auditor without importing the closure builder's fitting/selection functions; independently re-read and recompute hashes, key counts, cell support, effect direction/interval logic, and final labels.
- [ ] Verify canonical r3 hashes, source/wrapper/executor/manifest/inventory freeze, prior r3 QA PASS, no raw-IQ/20.46 execution flags, and no writes outside the new namespace plus explicitly authorized docs/scripts/tests.
- [ ] Run the auditor and require `INDEPENDENT_QA=PASS`.
- [ ] Run fresh py_compile and all relevant pytest tests, then inspect git diff/status for accidental changes.

### Task 8: Stop at Phase‑1 closure

**Files:**
- Read final: `docs/PHASE1_TRADITIONAL_CHANNEL_MODELING_SCIENTIFIC_CLOSURE.md`
- Read final: `dataset_generation_logs/channel_modeling/phase1_scientific_closure_20260830_r1/independent_qa_result.json`

**Interfaces:**
- Produces: final completion report only; no new execution request, AI model, 20.46 MHz run, or data collection.

- [ ] Report exact artifact paths and hashes, QA status, scientific controlled values, Handoff impact, and the next decision owner.
- [ ] Stop and wait for Commander instruction.

