# Mainline Stage2 WP3 — Environment, Geometry, and Motion Conditions

## Binding scope

Implement the Commander-approved WP3 attachment dated 2026-10-28. The existing V0/WP2 evidence and frozen Stage2 CSV extracts are the input; the attachment is the scientific specification. The primary population is the six Urban and three Mountain/Valley scenes. Highway/Open and Special Reflective remain descriptive/applicability supplements. Do not touch Task 5 production or use MATLAB, SAGE, CIR, GNSS-SDR, raw IQ, MAT, or HDF5 payloads.

## Global constraints

- Work only in `C:/Users/Jing_/.codex/worktrees/gnss-cir/GNSS_Multipath_Project`, on the existing `review/gnss-mainline-cir-model-20261022` branch. Preserve all pre-existing modifications and untracked outputs.
- Use the accepted V0 path/window extracts, geometry/trajectory overlays, and WP1/WP2 outputs with SHA provenance. Do not rerun V0 or WP2.
- Use exact scene holdout; compare models on identical eligible test paths; report per-scene and macro-scene scores. Never infer independent-row uncertainty from paths, windows, or overlapping LOSO folds.
- For parameter fitting and held-out scoring, conditions are window-level: give each scene equal total weight, each MPC-bearing selected window equal within-scene weight, and split that window's weight across its MPC rows. Label this as a descriptive window/scene-balanced pseudo-likelihood, not an independent-observation likelihood.
- GSV-measured elevation is the primary angle source. Keep ephemeris-derived, GGA-height, zero-height, and missing sources separate. Motion is descriptive unless source uniqueness, quality, coverage, and within-scene variation support a defensible window-level model.
- Preserve all core and supplement records; no post hoc exclusions, no Stage0 zero-MPC imputation, and no unapproved joint/correlation model.
- Write new code, results, and test evidence only in new WP3 paths. Update the authoritative Master Plan, Engineering Handoff, and Paper Handoff with evidence-bounded status.

## Execution tasks

### Task 1 — Reconfirm inputs and contract tests

Read local repository guidance and existing V0/WP2 interfaces. Add focused tests first for identity-preserving joins, environment scopes, source separation, and scene-fold membership using small synthetic fixtures. Run the new tests and confirm expected RED failures before implementation.

Expected: exact 8,914-path/7,847-window source package and hashes match existing manifests; no WP3 result package is overwritten; tests fail for absent WP3 behavior, not fixture errors.

### Task 2 — Build WP3 support and condition dataset

Implement a pure Python module that validates unique `(run_id, window_id, path_id)` identities, binds each path to its selected window, retains the four environment groups, and creates scene/environment/source support tables. Summarize measured and derived elevation separately, height source, missingness, and motion-source reuse. Keep motion descriptive if the verified evidence does not support modeling.

Expected: all 8,914 Stage2 MPC and 7,847 windows remain represented; core and supplement counts reconcile to source extracts; no Stage0 windows or science payloads are read.

### Task 3 — Implement and test bounded M0/M1/M2 fits

Reuse the accepted WP1/WP2 marginal families and scoring conventions. Implement scene/window-balanced marginal M0, environment-specific M1, and a simple environment plus continuous-elevation M2 only on source-specific support. Fit every fold without its held scene. For M0/M1 comparisons with M2, refit and score on the same eligible rows. Keep measured GSV, ephemeris/GGA-height, and ephemeris/zero-height in separate sensitivity strata; do not merge sources or force unsupported strata. Add tests for weighted fits, positive-domain delay, signed Doppler/power, held-scene exclusion, and same-row pairing.

Expected: every test has an observed RED then GREEN; unsupported/nonconvergent fits remain explicitly recorded. No condition is retained solely for in-sample fit improvement.

### Task 4 — Run bounded real-data LOSO analysis

Run the new analysis once on the pinned small CSV extracts. Evaluate complete-scene LOSO for all nine core scenes; report per-scene and equal-scene macro predictive log scores, parameter stability, tails/support, and source-specific coverage. Summarize the two supplementary environment groups descriptively and as applicability checks, without fitting separate models unless directly justified by the approved specification and support.

Expected: model comparisons use identical test identities within each paired comparison; the prior 13-scene global V0/WP2 benchmark is labeled as a different training population. No overlapping-fold confidence interval or path-row bootstrap is presented as independent-scene inference.

### Task 5 — Reproducible results and focused validation

Create a new timestamped WP3 result package containing the Chinese report, parameters, per-scene/fold scores, support/condition tables, useful figures, run manifest with input/code/output hashes, and exact test/run logs. Independently recount identities, environment counts, fold coverage, and score aggregates from written outputs.

Expected: rerun is deterministic for tabular outputs given pinned inputs and code; the package records failures/limitations and does not claim Gate G or WP6 completion.

### Task 6 — Update long-term handoffs

Update only the WP3 status/evidence sections of `docs/ACADEMIC_CHANNEL_MODELING_MASTER_PLAN.md`, `docs/GNSS_SAGE_ENGINEERING_HANDOFF_CURRENT.md`, and `docs/GNSS_SAGE_PAPER_HANDOFF_CURRENT.md`. Preserve prior history and pre-existing user edits. Record actual analysis status, exact paths/hashes, real results, test evidence, limitations, and the next single priority.

Expected: documents distinguish WP3 results from CIR/Gate E/F, alpha, and WP6; no status is marked complete before evidence and independent review.

### Task 7 — Final audit

Run focused WP3 tests, `py_compile`, `git diff --check`, reconcile manifests and reports, and review the complete WP3 diff separately from pre-existing changes. Recheck Task 5 using a brief read-only process/snapshot sample; do not interact with production. Do not commit or push unless the diff can be safely isolated from all prior unrelated user changes; report the actual Git/PR state.

Expected: no Task 5 production changes; clean WP3-specific validation; all scientific claims trace to outputs; any remaining limitation is stated explicitly.

## Review focus

- Data leakage across scene folds or across GSV/ephemeris sources.
- Effective sample-size overstatement from multiple paths, PRNs, or overlapping windows.
- Candidate models not scored on the same held-out identities.
- Scene/environment weights that let one large scene dominate.
- Conditional model instability with only three Mountain/Valley scenes.
- Motion values that reuse a small number of NMEA records or show questionable ranges.
- Supplement environments being silently dropped or misrepresented as core inference.
- Prior Task 5 production data or pre-existing worktree changes being modified.
