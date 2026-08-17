---
name: vtc2027-paper-authoring
description: "Guide VTC2027-Spring Regular Paper writing, LaTeX, figures, tables, evidence-driven results, references, and submission QA in E:\\GNSS_Multipath_Project. Use for tasks editing or auditing docs/vtc2027_spring, preparing VTC evidence or manuscript content, selecting figures, checking references, compiling IEEEtran, or making submission-readiness decisions."
---

# Vtc2027 Paper Authoring

Use this skill to keep the VTC2027-Spring Regular Paper concise, evidence-driven, reproducible, and inside its frozen scope. Treat the VTC paper as a focused path-extraction and experimental-characterization paper, not as the complete long-term GNSS channel-modeling project.

## Frozen submission target

- Venue: VTC2027-Spring Regular Paper.
- Official deadline: 2026-09-01; internal final review: 2026-08-31; notification: 2026-12-20.
- Target length: 5 IEEE conference pages. Do not expand to 7 pages without explicit Commander approval.
- Use IEEE conference style and preserve the IEEE template. Compress content and optimize layout before considering any format change.

## State sources and startup protocol

Before any VTC paper task:

1. Read `docs/vtc2027_spring/VTC_PLAN.md` and `docs/vtc2027_spring/EVIDENCE_MATRIX.md` first. Read `README.md`, `VTC_PRODUCTION_PRIORITY_QUEUE.md`, `MANUSCRIPT_OUTLINE.md`, `FIGURE_TABLE_PLAN.md`, `manuscript/`, or `submission/` as needed for the requested task.
2. Check the current submission gate and evidence stop condition. Do only the smallest step needed for that gate; do not add production or analysis merely because it is possible.
3. Use `docs/GNSS_SAGE_PAPER_HANDOFF_CURRENT.md` as the paper/science status source and `docs/GNSS_SAGE_ENGINEERING_HANDOFF_CURRENT.md` for engineering execution facts. Do not create parallel paper status, roadmap, or final-state files.
4. Rebuild claims from current artifacts and QA reports. Never rely on an old handoff when a current evidence matrix, receipt, or QA artifact contradicts it.

## Frozen VTC scope

The paper studies:

```text
real dynamic GPS L1 C/A raw-IQ measurements
  -> GNSS-SDR support
  -> NAV-aided hierarchical SAGE
  -> path-level multipath characterization
```

The long-term project may continue toward an event/path database and environment/elevation-conditioned statistical GNSS channel model, but those are not the VTC paper's required deliverables. Keep the following out of scope unless the Commander explicitly changes the scope:

- complete stochastic channel modeling, full PDP/RMS-delay-spread modeling, or fitted distribution families;
- Ricean K-factor modeling as a completed result;
- AIC/K-S model selection, full path-arrival processes, or synthetic channel generation;
- multipath mitigation, positioning-accuracy improvement, receiver redesign, tracking-loop optimization, or a new SAGE algorithm;
- complete 20.46 MHz analysis and unrelated new receiver, speed, CN0, or environment-taxonomy branches.

Do not claim to have invented SAGE. Present SAGE as the high-resolution path-extraction tool connecting measured GNSS IQ to physical path observations.

## Paper question and fixed contributions

Keep the paper centered on whether physically consistent multipath components can be extracted and confirmed from real dynamic GPS L1 C/A raw IQ using a NAV-aided hierarchical SAGE framework, and what path-level propagation characteristics are observed across realistic environments and satellite geometries.

Preserve three contribution classes:

1. A real dynamic GPS L1 C/A measurement and processing chain: RF-Catcher V2, 1575.42 MHz, 10.23 MHz, interleaved int16 IQ, vehicle-mounted RHCP roof antenna, GNSS-SDR preprocessing, and realistic environment classes, only where the current artifacts support the fact.
2. A NAV-aided hierarchical SAGE path-extraction framework with the Stage0–Stage4 reliability hierarchy.
3. Measurement-based path-level multipath characterization using confirmed event/path counts and, where supported, excess delay, relative Doppler, relative power, temporal persistence, and bounded environment/elevation comparisons.

Working titles may remain flexible. Preserve the scope of `SAGE-Based High-Resolution Multipath Characterization of GPS L1 C/A Signals in Dynamic Vehicular Environments` and its measurement-based alternative; never silently broaden the title into complete channel modeling.

## Manuscript structure and page discipline

Use the compact conference structure unless the current VTC outline explicitly changes it:

```text
I. Introduction                          ~0.6 page
II. Measurement and Processing Framework ~0.9 page
III. Hierarchical SAGE Multipath Extraction ~1.0 page
IV. Experimental Results                 ~1.9 page
V. Conclusion                            ~0.25 page
References and layout remainder
```

Results is the priority. Avoid letting methodology consume the page budget. The expected results organization is:

- A. Hierarchical Filtering Validation
- B. Representative Multipath Extraction
- C. Path-Level Multipath Characteristics
- D. Environment and Elevation Dependence, renamed to `Environment-Dependent Observations` if event-level elevation evidence is insufficient.

## Evidence and scientific wording

- Every number, comparison, and conclusion must trace to a current artifact, execution receipt, independent QA report, evidence matrix entry, or posterior replay. Mark missing metadata as missing; do not infer it from a filename.
- Keep status words distinct: `Completed/Validated`, `Implemented`, `Planned`, `Not started`, and `Failed/Frozen`.
- Stage2 `L>=2` is a model-selection result, not confirmed multipath. Stage3 reliable centers are persistent candidates, not confirmed multipath.
- Use the current confirmed criterion exactly: `joint_valid == 1` AND `joint_multipath_count > 0` AND a matching Stage4 path has `is_multipath == 1`. Only then count a confirmed event/path.
- For a valid zero-event task write: “under the current Stage4 confirmation criterion, this task produced zero confirmed multipath events.” Do not write “no physical multipath,” “LOS proven,” “no reflections,” or that an environment or satellite eliminates multipath.
- Do not turn production governance, QA, or a single task into a universal scientific claim. A representative case is illustrative, not dataset-wide evidence.
- Scene-level or PRN-level mean elevation is not event-level elevation. Make an event-level elevation claim only after window-level TOW/geometry alignment is independently QA-verified; otherwise report bounded environment observations without asserting elevation dependence.
- VTC may use descriptive statistics, counts, medians, ranges, empirical CDFs, scatter, and box plots. Do not present fitted stochastic distributions or a complete channel parameterization as VTC results unless the evidence matrix explicitly supports them.

## GNSS/SAGE method boundary

Describe the pipeline as raw IQ -> GNSS-SDR tracking/navigation support -> NAV-aided SAGE -> Stage0–Stage4 evidence -> confirmed path parameters. Preserve the hierarchy and explain that the final scientific object is a physically traceable path observation, not a binary receiver indicator.

Do not alter algorithm or confirmation rules in a paper edit. Do not use unconfirmed Stage2/Stage3 outputs to inflate event counts, and do not use unscanned or not-promoted windows as LOS or no-event evidence.

## Figures and tables

Keep only figures that add information:

- Figure 1: measurement, GNSS-SDR, and hierarchical SAGE processing pipeline;
- Figure 2: a QA-passed representative confirmed multipath case;
- Figure 3: hierarchical filtering, rejection, and confirmation;
- Figure 4: path-level characterization, preferably excess delay, relative power, relative Doppler, and environment, with elevation only if its evidence gate passes;
- Table I: measurement and processing configuration; add other tables only when they reduce ambiguity or repetition.

Select Figure 2 by traceability, complete Stage4 path parameters, clear interpretation, and QA PASS—not merely visual attractiveness. State that it is representative and do not hide other results from the same task.

## LaTeX and reference rules

- Formal source path: `docs/vtc2027_spring/manuscript/latex/`, especially `main.tex`, `references.bib`, and `figures/`.
- Use IEEEtran conference mode. After material text/figure/table changes, compile when the environment is available and record the resulting page count. Never shrink fonts, margins, or line spacing illegally.
- In `references.bib`, never invent DOI, volume, issue, pages, year, or author metadata. Mark unresolved entries `METADATA_TO_VERIFY` and verify from the original paper, IEEE, ION, official GNSS-SDR documentation, or primary equipment/manual sources.
- Do not put request IDs, hashes, receipt mechanics, or engineering-log prose in the manuscript. Use those only to support internal traceability and evidence QA.

## Frozen production and submission route

Follow this order and stop when the minimum evidence condition is met:

```text
necessary T1 evidence production
 -> independent QA
 -> evidence stop decision
 -> confirmed event/path aggregation
 -> event-level geometry QA
 -> final VTC subset
 -> Figures 2–4 and Results
 -> 5-page manuscript
 -> scientific consistency QA
 -> reference/format/language QA
 -> internal final by 2026-08-31
 -> submit before 2026-09-01
```

Do not automatically create production requests, start another task, resume an old task, or expand the queue from a writing task. Production remains governed by immutable request/manifest, `new_only=true`, `resume_allowed=false`, one-task-at-a-time execution, normal Windows-user MATLAB wrapper, and independent QA. Never call MATLAB/SAGE from the Codex sandbox.

After VTC submission, the long-term project may resume complete event/path database construction and statistical GNSS multipath channel modeling. Do not make VTC scope permanent project scope.

## Task completion and handoff behavior

For each task, report changed files, evidence sources, claims that remain unavailable, and the next minimum necessary step. Update the Paper Handoff when scientific route, paper contribution, chapter state, or new paper-usable facts change. Update `PAPER_WORKSPACE_INDEX.md` only when the paper asset structure changes. Update Engineering Handoff only for an actual engineering capability or execution-state change; a manuscript-only edit normally does not require it.

Never create duplicate files such as `PAPER_STATUS_NEW.md`, `PAPER_PLAN2.md`, `FINAL_STATUS.md`, or replacement database schemas. End task reports with:

```text
Handoff impact:
- Engineering handoff update required: yes/no
- Paper handoff update required: yes/no
```

If no experiment was requested, explicitly state that raw IQ was not read, MATLAB/SAGE/batch were not run, and production artifacts were not modified.
