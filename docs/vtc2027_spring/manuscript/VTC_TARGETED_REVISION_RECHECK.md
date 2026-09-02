# VTC Targeted Revision Re-check

**Review date:** 2026-08-16  
**Previous simulated recommendation:** `BORDERLINE`  
**Current simulated recommendation:** `WEAK ACCEPT`  
**Review type:** Targeted re-check of the original 4 HIGH, 6 MEDIUM, and 3 LOW issues. This is not a real editorial decision.

## 1. Scope and integrity boundary

The revision used only the existing VTC evidence package, current manuscript source, existing figures/tables, verified references, and the previous comprehensive review. No raw IQ was read, no MATLAB/SAGE/batch task was run, no new path was selected, no threshold or confirmation criterion was changed, and no production artifact was modified. The five confirmed paths, the G18 zero-confirmation case, the G28 Stage4 non-confirmation case, all table values, and all figure data remain unchanged.

The English LaTeX source remains the formal source of truth. The Markdown draft was synchronized with the same scientific text, and the Chinese file is a user review copy only.

## 2. REVIEW_ISSUE_ACTION_MATRIX

| Issue ID | Severity | Section / asset | Reviewer concern | Planned action | Scientific evidence needed | New experiment required | Manuscript change | Status |
|---|---|---|---|---|---|---|---|---|
| H-01 | HIGH | Abstract, IV-C, V | Five paths could be read as an over-broad characterization claim. | Reframe the result as bounded descriptive path-level demonstration and state what it does not estimate. | Existing five Stage4-confirmed paths, three cases, G18 zero-confirmation, and existing limitations. | NO | Added “descriptive,” “bounded,” no population/ranking/probability/model language. | CLOSED |
| H-02 | HIGH | Abstract, II-D, III-B | NAV-aided role might appear to be a label rather than an operational dependency. | State the input-to-operation chain. | Existing tracking/telemetry, decoded NAV, PRN/channel, Stage0 and provenance facts. | NO | Added synchronization/sample support, NAV wiping, 40-ms windows, stream association, and pre-SAGE role. | CLOSED |
| H-03 | HIGH | III-C/D | Stage4 could look like a software-field gate without scientific justification. | Explain temporal persistence and joint multi-snapshot consistency without claiming ground truth. | Existing Stage3 persistence, approximately 100-ms Stage4 joint estimation, and fixed criterion. | NO | Added local-fit versus joint-support rationale and conservative wording. | CLOSED |
| H-04 | HIGH | II-C, IV-D, V | Partial geometry could be overread as event-level elevation or environmental evidence. | Keep geometry as a limitation and narrow cross-case language. | Existing `PARTIAL` geometry status and scene-level contexts. | NO | Renamed IV-D and removed causal/ranking implications. | CLOSED |
| M-01 | MEDIUM | III, Table I | Exact search grids/tolerances are not fully reproducible from five pages. | Disclose the parameters that determine method interpretation without inventing undocumented values. | Existing 40-ms window, approximately 100-ms joint interval, L=1--4, persistence, and relative-Doppler semantics. | NO | Preserved/clarified these high-impact parameters; exact undocumented grids remain outside the paper. | PARTIALLY_CLOSED |
| M-02 | MEDIUM | I | Research gap was implicit. | Distinguish established SAGE from the present measurement-to-evidence organization. | Existing verified SAGE and GNSS multipath references. | NO | Added a restrained gap sentence; no “first” or absolute prior-work claim. | CLOSED |
| M-03 | MEDIUM | Figure 2 | Sparse figure may not make the direct/secondary relationship clear. | Improve caption and surrounding explanation without fabricating a curve. | Existing Stage4 path-table parameters only. | NO | Caption now states the compact direct/secondary purpose and unavailable-curve boundary. | PARTIALLY_CLOSED |
| M-04 | MEDIUM | Figure 4 | Five points could be mistaken for a statistical plot. | Make the descriptive/no-fit/no-population interpretation explicit. | Existing five path rows and figure-generation manifest. | NO | Caption and IV-C now say descriptive five-point view, no fit/trend/population inference. | CLOSED |
| M-05 | MEDIUM | II-B | Time synchronization/front-end details are not documented. | Mark the information as unavailable rather than guessing. | Existing evidence package explicitly omits these details. | NO | Existing limitation remains explicit; no unsupported setup claim was added. | PARTIALLY_CLOSED |
| M-06 | MEDIUM | Figure 3, IV-A | Stage2 evaluations could be confused with unique candidate counts. | Separate the side annotation from the unique-object funnel. | Existing figure data and Stage2 accounting semantics. | NO | Caption and IV-A now state that Stage2 evaluations are not an additional candidate set. | CLOSED |
| L-01 | LOW | Captions and IV | Repeated limitations consume page space. | Compress repeated wording while retaining the boundary. | Existing claims and captions. | NO | Reduced repetition while preserving all key limitations. | CLOSED |
| L-02 | LOW | IV-A, V | Zero-event terminology varied. | Use operational zero-confirmation wording consistently. | Existing G18 QA/evidence wording. | NO | Retained “under the current Stage4 confirmation criterion...” wording. | CLOSED |
| L-03 | LOW | Table II, IV-A | Table and surrounding text partly duplicated. | Keep the useful table and shorten its surrounding explanation. | Existing task-level evidence summary. | NO | IV-A now assigns the table to context/count summary and avoids repeating its full role. | CLOSED |

**Issue closure:** HIGH remaining 0; MEDIUM remaining 3 partial; LOW remaining 0; CRITICAL remaining 0.

## 3. Main manuscript changes

### Abstract

The abstract now states exactly how tracking/telemetry, decoded navigation symbols, and PRN/channel association support NAV wiping and valid 40-ms window construction. It retains the five-path result and the valid zero-confirmation case, but explicitly calls the result descriptive and measurement-based.

### Introduction

The research gap now distinguishes established high-resolution/SAGE parameter extraction from the paper’s contribution: organizing real dynamic raw-IQ measurements, navigation support, and progressively stricter evidence into a traceable path-confirmation workflow. The three contributions remain unchanged in number and are more specific: measurement/processing basis, NAV-aided hierarchy, and bounded path-level characterization.

### Section II

The processing overview now exposes the actual interface:

```text
raw IQ
  -> tracking/telemetry and decoded NAV support
  -> NAV-aided Stage0
  -> hierarchical SAGE
  -> Stage4-confirmed path
```

The text explains that tracking/telemetry provide synchronization and sample support; decoded NAV symbols provide PRN/time alignment for NAV wiping and complete 40-ms Stage0 windows; PRN/channel association selects the intended stream; and RINEX/NMEA provide navigation/motion provenance. It continues to exclude broadcast-ephemeris reconstruction and event-level elevation claims.

### Section III

The NAV-aided initialization subsection now states where the information enters the pipeline and what it constrains before SAGE: known-symbol observation construction, code-aligned correlation support, fractional delay--Doppler evaluation support, intended stream selection, and valid interval. The stage descriptions now state both purpose and operation:

- Stage0 constructs valid observation units and prevents incomplete windows from becoming path evidence.
- Stage1 reduces the set entering the more expensive SAGE evaluation.
- Stage2 compares local fractional delay--Doppler models for (L=1,2,3,4); (L\geq2) remains intermediate model-order evidence.
- Stage3 rejects isolated or unstable higher-order behavior through temporal/power/neighbor consistency; a reliable center remains intermediate evidence.
- Stage4 checks whether a secondary component remains jointly supportable over approximately 100 ms.

The confirmation subsection now gives the scientific definition first: a valid joint multi-snapshot solution containing a secondary component that satisfies the current path-classification criterion. The implementation field names remain available as an audit mapping, but are no longer the explanation for why the result is trusted.

### Section IV

Section IV-A now explains why the reduction from Stage0 windows to Stage4 rows is meaningful as an evidence hierarchy, while explicitly refusing to interpret it as a measured false-positive rate or occurrence probability. The G25 window-985 discussion now explains that it is included because its Stage4 joint solution satisfies the fixed confirmation rule, not because its Stage2 model order alone is sufficient.

The five-path paragraph now states that the values are not fitted distributions, population estimates, environment rankings, or environment-wide trends, and that the small retained set is the consequence of stricter evidence. Section IV-D is now titled `Observations Across the Evaluated Cases` and avoids causal or richness-ranking language.

### Conclusion

The conclusion now describes the hierarchy as progressively stricter validity, local-model, temporal-persistence, and joint-consistency evidence. It calls the result a bounded descriptive path-characterization demonstration and explicitly excludes a complete channel model, environment ranking, and elevation-dependent statistical law.

## 4. NAV-aided clarification

In the revised paper, “NAV-aided” has the following concrete meaning:

1. Tracking and telemetry products provide synchronization and sample support.
2. Decoded navigation symbols provide PRN/time-aligned known symbols for NAV wiping and complete 40-ms Stage0 window construction.
3. PRN/channel association selects the intended tracking stream and constrains the valid interval.
4. These inputs enter before the SAGE fit and provide a common known-symbol observation unit for correlation and fractional delay--Doppler evaluation.
5. RINEX and NMEA provide navigation/motion provenance; NMEA/GSV geometry diagnostics are not used here to claim event-level elevation.

The revised text does not claim event-level geometry reconstruction, complete ephemeris-based trajectory reconstruction, precise TOW-to-UTC synchronization, or broadcast-NAV-derived event elevation.

## 5. Stage4 scientific rationale

Stage2 provides local model-order evidence within a screened window, while Stage3 asks whether the estimated behavior persists across neighboring windows. Stage4 extends this logic to a multi-snapshot joint solution over approximately 100 ms: an isolated local fitting artifact need not remain jointly supportable, whereas a retained secondary component should show compatible delay, Doppler, and path behavior across the joint snapshots. The resulting rule is a conservative joint-consistency criterion, not a mathematical guarantee of true multipath or an external-ground-truth validation.

## 6. Small-sample framing

The revised manuscript keeps the number visible: five Stage4-confirmed path rows across three representative scenario contexts, plus a valid G18 zero-confirmation case and the G28 Stage4 non-confirmation example. These cases demonstrate hierarchical extraction behavior, provide traceable confirmed examples, and report path-level parameters for the evaluated cases. They are not used for population statistics, environment ranking, probability estimation, or statistical channel modeling. The small retained set is explained as the result of conservative progressive evidence filtering.

## 7. Figure and table changes

No figure data, table values, figure-generation script, or figure-generation manifest was changed.

| Asset | Action in this revision | Result |
|---|---|---|
| Figure 1 | KEEP; caption clarified | Caption now names tracking/telemetry and decoded NAV support. The existing graphic already shows GNSS-SDR tracking/NAV support. |
| Figure 2 | REVISE caption and narrative | Direct/secondary relationship and Stage4 confirmation role are clearer; no unavailable correlation/residual curve was added. |
| Figure 3 | KEEP with caption revision | Main flow and Stage2 side annotation are explicitly separated. |
| Figure 4 | REVISE caption and narrative | It is identified as a descriptive five-point view; no fit, trend, or distribution was added. |
| Table I | KEEP with one wording clarification | Products row now identifies tracking/telemetry; configuration values are unchanged. |
| Table II | KEEP | It remains the compact task-level evidence summary; values and context labels are unchanged. |

Because only text/captions changed, the figure source files, figure-generation manifest, and evidence data do not require new hashes or replacement.

## 8. Terminology and claim audit

- `NAV-aided` is the single main term; `NAV-assisted` was not introduced as a competing label.
- `candidate`, `reliable center`, `Stage4-confirmed path`, `joint confirmation`, `excess delay`, `relative Doppler`, `relative power`, and `coherence` retain their existing meanings.
- Stage2 (L\geq2) remains model-order evidence, not confirmed multipath.
- Stage3 reliable centers remain intermediate evidence, not confirmed multipath.
- G18 remains an operational zero-confirmation case and is not described as LOS or physically multipath-free.
- The revised manuscript avoids unsupported `novel`, `first`, `effective`, `robust`, `accurate`, and `significant` performance claims.
- `characterization` is consistently bounded by “path-level,” “descriptive,” “evaluated cases,” or equivalent scope language.
- `environment` refers to scenario-level context; `elevation` remains explicitly limited by partial geometry.
- `statistical channel model` remains future work, not a completed result.

## 9. Page and compile status

The revised source was compiled in an isolated directory using:

```text
pdflatex -> bibtex -> pdflatex -> pdflatex
```

All four commands exited with code `0`. The final PDF has **5 pages**, US Letter portrait, is unencrypted, and is PDF 1.7. The final log contains:

- LaTeX errors/fatal errors: 0
- BibTeX errors/warnings: 0
- Undefined citations in final pass: 0
- Undefined references in final pass: 0
- Overfull boxes: 0
- Underfull boxes: 7

Figures 1--4 and Tables I--II were rendered at the actual page scale and checked visually. Text, captions, labels, table values, representative path values, and references remain readable. The fifth page is a figure-focused page with substantial whitespace; this is a camera-ready layout polish item, not a scientific or evidence defect.

Updated candidate PDF:

`docs/vtc2027_spring/submission/VTC2027_Spring_submission_candidate.pdf`

New SHA-256: `4134A3729474AAFD280048C645AFF5750FFEAA35F8F6DAE1B689BB3E8508456F`  
Previous SHA-256: `A9119E0B82B60BF9EB991A80BCCFA54CE751944DDE8786A2CCBF9E63144B57C8`

## 10. Updated reviewer re-check

The revised manuscript improves the original BORDERLINE concerns without adding evidence or scientific claims. The most defensible simulated recommendation is now **WEAK ACCEPT**, conditional on final author/template/portal completion and ordinary camera-ready layout polish. This is not a prediction of the actual VTC decision.

The recommendation is not raised to ACCEPT because the five-path evidence set and partial event-level geometry remain genuine limitations, and exact search-grid/tolerance disclosure is still incomplete in the five-page source.

## 11. Remaining issues

### PARTIALLY_CLOSED

- **M-01:** The paper discloses the parameters needed to understand the method—40-ms windows, approximately 100-ms joint confirmation, L=1--4, persistence, and relative-Doppler semantics—but does not list every exact grid and tolerance. No undocumented value was invented.
- **M-03:** Figure 2 now clearly states its direct/secondary path purpose and unavailable-curve boundary, but the underlying five-parameter visual remains intentionally compact.
- **M-05:** Time synchronization and additional front-end details remain unavailable. The paper explicitly marks them as undocumented rather than implying a false reproducibility detail.

### OPEN outside the original issue matrix

- Author name, affiliation, correspondence address, and email remain placeholders.
- Portal-specific author visibility, template, upload, and PDF-compliance requirements remain to be confirmed.
- Final camera-ready layout may reduce the fifth-page whitespace and address the seven underfull-box warnings.

These are submission-administration/layout blockers, not reasons to run a new SAGE experiment in this revision.

## 12. Readiness

```text
HIGH_ISSUES_REMAINING = 0
MEDIUM_ISSUES_REMAINING = 3  # all PARTIALLY_CLOSED, none requires new evidence for current scope
CRITICAL_ISSUES = 0
NEW_EXPERIMENT_REQUIRED = NO
UPDATED_CHINESE_REVIEW_READY = YES
REVISION_RECHECK_READY = YES
SUBMISSION_SCIENTIFIC_CONTENT_READY = YES
NEXT_VTC_DECISION_REQUIRED = YES
```

## 13. Files and execution record

Modified or generated paper assets:

- `docs/vtc2027_spring/manuscript/VTC2027_Spring_draft.md`
- `docs/vtc2027_spring/manuscript/latex/main.tex`
- `docs/vtc2027_spring/manuscript/VTC2027_Spring_CN_REVIEW.md`
- `docs/vtc2027_spring/manuscript/VTC_TARGETED_REVISION_RECHECK.md`
- `docs/vtc2027_spring/submission/VTC2027_Spring_submission_candidate.pdf`
- `docs/GNSS_SAGE_PAPER_HANDOFF_CURRENT.md` (status synchronization only)

Not modified: production manifest, execution requests, SAGE outputs, figures/data sources, figure-generation manifest, references, Engineering Handoff, or `PAPER_WORKSPACE_INDEX.md`.

Execution record:

- raw IQ read: no
- MATLAB: no
- SAGE: no
- batch production: no
- new experiment: no
- production artifact modified: no

## 14. Subsequent author follow-up revision

After the previous targeted revision check, the author requested three presentation adjustments to the synchronized manuscript sources:

1. remove the redundant environment-category preview from Section II-A;
2. shorten the Table II caption and move the definition of an independent measurement run and the path-counting rule into Section IV-A;
3. state the representative confirmed-multipath retention cases in Section IV-A before describing the G28/G18 final non-confirmation cases.

The English LaTeX source, Chinese review LaTeX source, and both Markdown mirrors were updated consistently. Table II values, figure assets, evidence files, and scientific conclusions were not changed. The updated English and Chinese canonical PDFs were compiled with the existing `pdflatex -> bibtex -> pdflatex -> pdflatex` and `xelatex -> bibtex -> xelatex -> xelatex` chains, respectively; all commands exited with code `0`, and both PDFs remain **4 pages**.

Final PDF hashes:

- English `docs/vtc2027_spring/manuscript/latex/main.pdf`: `861945F40B9F54BD02C45A00988A001DCE9A4E6ADF6470CD5BDDC2AC4DBB5A3F`
- Chinese `docs/vtc2027_spring/manuscript/latex_cn_review/main_cn_review.pdf`: `97B153021D37C0CFADC53A0738F239525B3D27290B60A2DD217FF01F1D230FDC`

The final English pass has no LaTeX error, fatal error, undefined citation/reference, or overfull box; three underfull-box warnings remain. The Chinese pass has no compilation error and retains the known font fallback warnings.

```text
SCIENTIFIC_CONTENT_CHANGED = NO
SCIENTIFIC_DATA_CHANGED = NO
FIGURE_DATA_CHANGED = NO
TABLE_DATA_CHANGED = NO
NEW_EXPERIMENT_EXECUTED = NO
RAW_IQ_READ = NO
MATLAB_EXECUTED = NO
SAGE_EXECUTED = NO
PRODUCTION_EXECUTED = NO
```
