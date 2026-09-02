# VTC2027-Spring Full-SAGE Evidence Assessment and Manuscript Update Plan

**Date:** 2026-08-25  
**Scope:** Read-only evidence assessment first; manuscript revision only after data gates pass and the author approves the evidence snapshot.  
**Out of scope:** New SAGE execution, MATLAB execution, raw-IQ reads, 20.46 MHz processing, estimator changes, occurrence-rate modeling, and stochastic channel modeling.

## 1. Decision summary

The newly completed SAGE corpus is large enough to justify a paper-data update assessment. The current manuscript reports 11 measurement runs, 17 analyzed PRN tracks, 12 positive tracks from 8 runs, 30 jointly confirmed paths, and 7/14/2/7 paths across Urban, Mountain/Valley, Highway/Open, and Reflective-Feature, respectively.

The current authoritative production summary contains an **upper-bound snapshot** of 13 runs, 77 unique result directories/PRN tracks, 117 confirmed events, and 123 confirmed paths. Its environment-level upper-bound counts are:

| Environment | Runs | Tracks | Positive tracks | Confirmed events | Confirmed paths |
|---|---:|---:|---:|---:|---:|
| Urban | 6 | 31 | 17 | 47 | 49 |
| Mountain/Valley | 3 | 19 | 13 | 24 | 25 |
| Highway/Open | 2 | 12 | 3 | 6 | 6 |
| Special Reflective | 2 | 15 | 10 | 40 | 43 |
| **Upper-bound total** | **13** | **77** | **43** | **117** | **123** |

These numbers are not yet manuscript-ready. The summary mixes formal production and validated evidence scopes and includes at least one protected historical result. The final paper set must be produced by the event/path database rules and an independent eligibility audit, not by copying the upper-bound counts.

**Recommended decision:** update Table II, Figure 4, and the bounded descriptive Results text if the strict eligible set passes the gates below. Keep the paper positioned as path extraction, validation, and descriptive path-level characterization; do not convert the larger corpus into an occurrence-rate or statistical-channel-model claim.

## 2. Authoritative inputs

- Mainline task: `主线` (`01a01348-48bd-73e2-851f-752ffdf9ec5d`)
- Engineering state: `docs/GNSS_SAGE_ENGINEERING_HANDOFF_CURRENT.md`
- Paper state: `docs/GNSS_SAGE_PAPER_HANDOFF_CURRENT.md`
- VTC writing state: `docs/GNSS_SAGE_VTC_WRITING_HANDOFF_CURRENT.md`
- Production census: `dataset_generation_logs/production_monitoring_10MHz/production_summary_10MHz.csv`
- Batch QA: `docs/10MHz_FULL_SAGE_UNATTENDED_BATCH_20260819_QA_REPORT.md`
- Scene/environment mapping: `dataset_generation_logs/production_planning_10mhz_20260812/scene_metadata_10MHz.csv`
- Database rules: `docs/MULTIPATH_EVENT_DATABASE_DESIGN.md`
- Existing VTC census and path evidence: `docs/vtc2027_spring/evidence/VTC_ENVIRONMENT_EVIDENCE_CENSUS.csv` and `docs/vtc2027_spring/evidence/VTC_ENVIRONMENT_PATH_CANDIDATES.csv`
- Canonical manuscripts: `docs/vtc2027_spring/manuscript/latex/main.tex` and `docs/vtc2027_spring/manuscript/latex_cn_review/main_cn_review.tex`

## 3. Inclusion policy to freeze

Use one manuscript analysis set with explicit eligibility rules:

1. Include only 10.23 MHz runs with complete Stage0--Stage4 artifacts and independent QA acceptance.
2. Require exact run identity and provenance linkage among summary, run context, Stage4 summary, Stage4 path table, request/receipt, and QA record.
3. Define a confirmed event only when `joint_valid=1`, `joint_multipath_count>0`, and the linked Stage4 path table contains the matching `is_multipath=1` path rows.
4. Count only Stage4 multipath path rows; never promote Stage2 high-order fits or Stage3 reliable centers.
5. Exclude `REJECTED_PROTECTED`, incomplete, schema-drifted, duplicate, or provenance-conflicted results.
6. Retain valid zero-event tracks in Table II coverage, but never describe them as physical no-multipath/LOS truth.
7. Recommend retaining scientifically usable Tier A and Tier B results when they share the frozen estimator and pass the same Stage4 and provenance gates. Report them as **analyzed PRN tracks**, not as formal-production tasks. Keep Tier C/historical-contract-caveat artifacts outside the primary comparison.
8. Treat measurement runs/scenes as the independent acquisition units. Confirmed paths are nested observations and must not be described as independent environment samples.

## 4. Execution plan

### Phase 0 — Wait for the mainline dry-run gate

- Let the active `主线` task complete database-rule freeze and its read-only validator.
- Do not duplicate or modify its validator, schema, Stage artifacts, or handoffs while it is active.
- Required gate: validator reproduces run/event/path counts from Stage4 and reports no unresolved key, count, unit, or provenance failures.
- If the gate fails, stop the paper update and use the validator issue list as the repair queue. Do not manually patch paper counts.

### Phase 1 — Freeze the VTC-eligible evidence snapshot

- Build the VTC analysis set from the validator/database export, not directly from the production summary.
- Assign every run one of: `INCLUDE_TIER_A`, `INCLUDE_TIER_B`, `EXCLUDE_TIER_C`, `EXCLUDE_QA`, or `PENDING_REVIEW`.
- Freeze unique keys for run, event, and path; check duplicate result directories and duplicate event/path identities.
- Join environment only through the human annotation source and retain its provenance/version.
- Produce a QA report containing:
  - included/excluded runs and reasons;
  - per-environment runs, analyzed tracks, positive tracks, events, and paths;
  - `joint_multipath_count` versus linked path-row consistency;
  - finite/range checks for excess delay, signed relative Doppler, and relative power;
  - zero-event and protected-result handling;
  - SHA-256 for the frozen census and confirmed-path export.

**Gate 1:** no unresolved QA or provenance failure; final counts are reproducible from frozen exports.

### Phase 2 — Decide the minimal scientific update

Prepare a one-page decision memo comparing the current 30-path set with the frozen expanded set:

- counts and environment coverage;
- parameter ranges, medians, and interquartile ranges;
- whether any current qualitative sentence changes direction;
- whether one environment remains too sparse for even bounded description;
- sensitivity of summaries when Tier B rows are excluded.

**Recommended claim boundary:** retain descriptive medians/ranges and individual path observations. Do not add p-values, environment ranking, causal language, path occurrence rates, or fitted channel distributions. If Tier-A-only and Tier-A+B summaries materially disagree, report the instability as a limitation or keep the current narrower set.

**Gate 2:** author approves the expanded evidence set and the exact claims before manuscript editing.

### Phase 3 — Update paper assets in temporary bilingual copies

Create fresh temporary copies from the canonical English and Chinese sources. Do not overwrite canonical files at this phase.

1. Update Table II from the frozen eligible census:
   - measurement runs;
   - analyzed PRN tracks;
   - confirmed events;
   - confirmed paths.
2. Regenerate Figure 4 only from the frozen eligible confirmed-path export:
   - retain the existing three parameters and environment order;
   - retain per-environment `n` and median markers;
   - use non-overlapping/jittered or semi-transparent points only as a display adjustment if needed;
   - do not alter any path value.
3. Update Section IV-D counts, ranges, medians, and bounded environment observations.
4. Update the abstract and conclusion only if they contain obsolete dataset-size facts or coverage wording.
5. Keep Figure 2 as the representative G25 confirmed case and Figure 3 as hierarchical behavior unless the expanded evidence audit finds a concrete factual issue. Do not replace them merely because more data exist.
6. Keep the controlled-recovery and native-model-support validation unchanged unless page pressure requires an author-approved compression; do not rerun validation.
7. Synchronize every factual change into the Chinese review source and Markdown mirrors.

### Phase 4 — Scientific, numerical, and layout QA

- Recompute all manuscript numbers directly from the frozen evidence export and compare them to Table II, Figure 4 labels, Results prose, abstract, and conclusion.
- Verify the paper still distinguishes runs, tracks, events, and paths.
- Verify zero-event wording, Stage4-only confirmation, signed Doppler, units, and environment labels.
- Compile English and Chinese LaTeX with the existing toolchain.
- Check page count (maximum five pages), figure order, float placement, citations/references, overfull boxes, and visual legibility at normal zoom.
- Generate a bilingual change report and PDF hashes for author review.

**Gate 3:** author reviews the temporary PDFs and approves canonical overwrite.

### Phase 5 — Canonical synchronization after approval

- Overwrite canonical English/Chinese sources and PDFs only after Gate 3.
- Update `EVIDENCE_MATRIX.md`, `VTC_PLAN.md`, VTC writing handoff, and paper handoff with the final frozen counts, evidence paths, hashes, and claim boundary.
- Update the engineering handoff only if the database/evidence workflow changes engineering state; a manuscript-only revision does not require it.
- Stop after final compile, evidence cross-check, and hash report. Do not start submission or any experiment.

## 5. Expected paper impact

The most likely useful revision is narrow but meaningful:

- Table II moves from a small selected evidence subset to a much broader QA-qualified coverage summary.
- Figure 4 becomes materially more credible because each environment has more path observations, especially Highway/Open and Special Reflective.
- Section IV-D can describe the expanded observed ranges and medians with less dependence on one or two tracks.
- The paper still must state that these are bounded descriptive observations, not independent-path inference, environment ranking, an occurrence-rate model, or a stochastic channel model.

No new SAGE experiment is required for this update. The remaining work is evidence qualification, aggregation, manuscript synchronization, and QA.

