# VTC2027-Spring Submission Workspace

This directory is the dedicated working area for the VTC2027-Spring Regular Paper submission. It is a paper-asset workspace, not a replacement for the project status documents and not a production execution system.

## Submission target

- Venue: VTC2027-Spring Regular Paper
- Submission deadline: 2026-09-01
- Internal complete-draft target: 2026-08-31
- Target length: five pages, including references according to the final venue template
- Primary technical area: Antenna Systems, Propagation, and RF Design
- Secondary areas: Positioning Technologies, Localization and Navigation; Signal Processing for Wireless Communications

Working title:

> SAGE-Based High-Resolution Multipath Characterization of GPS L1 C/A Signals in Dynamic Vehicular Environments

Alternative title:

> Measurement-Based Characterization of Dynamic GNSS Multipath Using High-Resolution SAGE Path Extraction

## Scope of this paper

The VTC paper is a focused conference paper about real dynamic GPS L1 C/A raw-IQ measurements, NAV-aided hierarchical SAGE processing, high-resolution path extraction, and measurement-based path-level characterization. The paper may discuss excess delay, relative Doppler, relative power, occurrence observations, and carefully bounded elevation/environment observations when the evidence matrix supports them.

The paper does not claim a new SAGE algorithm, a positioning or mitigation improvement, a complete statistical channel model, a synthetic channel generator, or a complete multi-scene event database. The full PDP/RMS-delay-spread/Doppler-spread/K-factor modeling program remains the longer-term journal/project objective.

## Authoritative documents

- `docs/GNSS_SAGE_PAPER_HANDOFF_CURRENT.md` — the unique paper/science status source.
- `docs/PAPER_WORKSPACE_INDEX.md` — the paper-asset navigation index.
- `docs/GNSS_SAGE_ENGINEERING_HANDOFF_CURRENT.md` — the unique engineering state source; this VTC workspace does not replace it.

The files in this directory organize the submission but must not be used to infer an experiment result that is not present in the authoritative handoff, an independent QA report, or a frozen artifact.

## Directory map

| Path | Purpose | Status |
|---|---|---|
| `VTC_PLAN.md` | Scope, contribution lock, timeline, gates, and evidence priorities | Implemented planning asset |
| `EVIDENCE_MATRIX.md` | Claim-to-artifact matrix and missing-evidence register | Implemented planning asset |
| `MANUSCRIPT_OUTLINE.md` | Five-page paper structure and section budgets | Implemented planning asset |
| `FIGURE_TABLE_PLAN.md` | Candidate figures/tables and source artifacts | Implemented planning asset |
| `manuscript/VTC2027_Spring_draft.md` | English manuscript skeleton and controlled placeholders | Implemented skeleton; results pending |
| `manuscript/latex/main.tex` | Independent IEEE conference-mode LaTeX manuscript skeleton | Implemented; compile pending toolchain |
| `manuscript/latex/references.bib` | Verified-reference staging file | Implemented; no verified entries imported yet |
| `submission/SUBMISSION_REQUIREMENTS.md` | Official VTC/IEEE requirements audit | Completed audit; template package pending |
| `submission/PAGE_BUDGET.md` | Five-page target budget and compression priorities | Implemented planning asset |
| `figures/` | Paper figure source and draft workspace | Figure 1 source/draft implemented; rendered PDF pending |
| `tables/` | Reserved table workspace | Not started |
| `evidence/` | Paper-facing evidence extracts, only after independent QA | Not started |
| `manuscript/latex/figures/` | Paper-side figure sources and draft copies | Implemented; PDF/render QA pending |
| `manuscript/latex/template_reference/` | Untouched official IEEE template archive and receipt location | Pending manual retrieval |
| `submission/` | Final PDF/source/package staging | Requirements audit implemented; final package not started |

## Current factual state at workspace creation

- The project has 19 scenes in the overall dataset, including 13 scenes at 10.23 MHz and 6 scenes at 20.46 MHz.
- The VTC production scope is the 10.23 MHz subset; the 20.46 MHz path is not part of this paper sprint.
- Reference-scene seven-PRN validation, Wave-A validation, and the first two formal 10.23 MHz production QA cases are available as evidence.
- Formal A3 G16 has a complete scientifically valid Stage0–Stage4 artifact and independent scientific QA, but its historical `resume_allowed=false` versus recorded `Resume=true` contract deviation means it is not Batch A continuous-production release evidence.
- The controlled G12 task has completed under normal Windows-user execution and passed independent QA: executor/task exit code 0, 21 output files, 3 confirmed events and 3 confirmed paths. It is available evidence, but is not yet promoted to a core VTC Results claim; the VTC evidence matrix remains the gate for inclusion.
- The raw-coarse/sampling v3 acceleration line is retained as a negative/limitation result and is not the production selector.
- Official submission requirements have been audited. No VTC-specific LaTeX class was found on the public official pages; the workspace uses the generic official IEEE conference convention pending manual retrieval of the IEEE package. No local TeX compiler is installed, so no PDF/page-count claim is made.

## Evidence discipline

Every numerical claim must point to an existing Stage CSV/MAT, execution receipt, independent QA report, or posterior replay artifact. Stage2 `L>=2` and Stage3 reliable centers are not confirmed multipath. A confirmed event/path uses the current Stage4 criterion only. A zero-event output is a valid pipeline outcome under that criterion and must not be rewritten as a physical claim that no multipath exists.

No experiment is executed by creating or editing this workspace. Production, MATLAB, raw-IQ, and SAGE actions remain governed by the engineering handoff and immutable execution/request rules.
