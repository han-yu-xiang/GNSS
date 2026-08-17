# VTC2027-Spring Submission Candidate Comprehensive Review

**Review date:** 2026-08-16  
**Review scope:** Current English submission candidate and its frozen evidence package.  
**Review type:** Simulated IEEE VTC reviewer review; this is not an actual editorial decision.  
**English source of truth:** `docs/vtc2027_spring/manuscript/latex/main.tex`  
**Companion user copy:** `docs/vtc2027_spring/manuscript/VTC2027_Spring_CN_REVIEW.md`

## 1. Review boundary and evidence basis

This review was performed without running MATLAB, SAGE, batch production, or any new experiment, and without reading raw IQ. The review used the current manuscript source, the verified reference file, the VTC plan and evidence matrix, the evidence README and manuscript tables/figure sources, the claim matrix, the reference verification matrix, the figure-generation manifest, and the current four-page submission-candidate PDF.

The manuscript is intentionally bounded. It presents real dynamic GPS L1 C/A raw-IQ measurements, GNSS-SDR support products, NAV-aided Stage0--Stage4 processing, and a small set of Stage4-confirmed path-level observations. It does not claim a new SAGE estimator, a complete statistical channel model, event-level elevation statistics, or a population-level environmental law.

## 2. Executive assessment

### Reviewer-style positioning

This is a measurement-based study asking whether physically traceable GNSS multipath components can be extracted from real dynamic GPS L1 C/A raw-IQ measurements using a NAV-aided hierarchical SAGE pipeline. Its central contribution is an evidence-disciplined Stage0--Stage4 path extraction and confirmation workflow with a small, QA-traceable set of path-level observations, rather than a new SAGE estimator or a completed channel model.

### Simulated recommendation

**Recommendation: BORDERLINE**

This recommendation is a cautious simulated review outcome, not a prediction of the real decision. The manuscript is technically coherent and can become a credible VTC submission through framing, explanation, and layout changes that use the existing evidence. The main risks are the small final path sample (five confirmed paths), partial event-level geometry, and the possibility that the Stage0--Stage4 hierarchy is read as an engineering orchestration rather than a clearly motivated scientific evidence framework. No new experiment is currently required to address the primary review risks; the manuscript must remain explicit about its bounded path-characterization scope.

### Three factors most likely to support acceptance

1. The paper uses a real dynamic GPS L1 C/A raw-IQ measurement chain and reports traceable path-level observations rather than only receiver-level degradation indicators.
2. The Stage0--Stage4 semantics and strict Stage4 criterion make the distinction between candidate, persistent intermediate evidence, and confirmed path auditable.
3. The manuscript is unusually disciplined about limitations: five paths are not presented as a population, G18 is a valid zero-confirmation case, and partial geometry is not turned into an elevation result.

### Three factors most likely to lead to rejection

1. A reviewer may judge five confirmed paths too small for the title-level word “characterization,” especially if the bounded scope is not prominent in the final version.
2. A reviewer may regard Stage0--Stage4 as heuristic software filtering if the scientific motivation for temporal persistence and Stage4 joint confirmation remains implicit.
3. A reviewer may find the contribution insufficiently novel if it is read as an application of established SAGE without a clear measurement/evidence-integration contribution.

### Main strengths

- Real dynamic GPS L1 C/A raw-IQ measurement chain rather than a purely synthetic demonstration.
- Clear distinction between Stage1 candidates, Stage2 model-order evidence, Stage3 reliable centers, and Stage4-confirmed paths.
- A strict and auditable confirmed criterion: `joint_valid == 1`, `joint_multipath_count > 0`, and a matching Stage4 path row with `is_multipath == 1`.
- Inclusion of both confirmed paths and valid non-confirmation/zero-confirmation cases.
- Traceable five-path observations, verified references, evidence tables, generated figures, and a four-page candidate PDF.
- Conservative treatment of geometry: LOW/MID/HIGH are scenario/PRN planning contexts, not event-level elevation measurements.

### Main weaknesses

- Only five Stage4-confirmed paths are available for path-level description, so the paper cannot support broad environmental or statistical conclusions.
- The manuscript explains what Stage4 records, but its scientific reason for using multi-snapshot joint confirmation should be stated more explicitly than the field-level criterion alone.
- The NAV-aided role is present but distributed across Sections II and III; a reviewer may still ask exactly which input supports which operation.
- Exact search grids, tolerances, and some implementation details are not disclosed in the five-page version.
- Geometry alignment is explicitly `PARTIAL`, which limits elevation-related interpretation but is handled honestly.

## 3. Scored review dimensions

Scores use a 1--5 scale: 1 = weak, 3 = adequate/borderline, 5 = excellent. These scores evaluate the present submission candidate, not the future research program.

| Dimension | Score | Strength | Weakness | Reviewer reason |
|---|---:|---|---|---|
| Relevance to VTC | 4/5 | Dynamic vehicular GNSS measurements, positioning/signal-processing relevance, and interpretable path parameters fit VTC interests. | The paper is not a vehicular-communications or positioning-improvement paper; track fit must be framed explicitly. | Strong application relevance, with a need to position the contribution around GNSS signal processing and measurement evidence. |
| Technical soundness | 4/5 | Signal model, NAV-aided initialization, stage semantics, and strict Stage4 criterion are internally consistent. | The final criterion is operational and lacks external electromagnetic ground truth or a measured false-positive benchmark. | Sound for a bounded characterization paper, not proof of universal physical truth. |
| Novelty and clarity | 3/5 | The integrated real-measurement/evidence workflow is a defensible systems contribution. | SAGE and the underlying estimator are established; Stage0--Stage4 may look like engineering orchestration unless its rationale is made explicit. | Novelty is adequate only when claimed as evidence-disciplined measurement methodology, not as a new SAGE algorithm. |
| Experimental credibility | 4/5 | QA-passed representative cases include positive and zero-confirmation behavior. | Three primary cases and five paths are a small evidence base. | Credible as a controlled demonstration; not sufficient for broad characterization. |
| Evidence sufficiency | 3/5 | Every central numerical claim is tied to the evidence package and claim matrix. | Sample size and partial geometry prevent population, probability, and elevation-law claims. | Sufficient for bounded claims, borderline for the title-level word “characterization.” |
| Method clarity | 4/5 | Stage0--Stage4, 40-ms windows, L=1--4, persistence, and approximately 100-ms joint confirmation are described. | Exact Stage1/Stage2 grids, tolerances, and some joint-estimation details are omitted. | Readable within a five-page limit, but a compact parameter disclosure would improve trust. |
| Reproducibility | 4/5 | Hardware/signal configuration, GNSS-SDR support chain, evidence sources, manifests, and QA artifacts are traceable. | A reviewer cannot reproduce every screening decision from the paper alone without exact grids and thresholds. | Strong provenance discipline; moderate method-detail gap. |
| Results quality | 3/5 | Representative path values, hierarchical filtering, rejection/non-confirmation, and zero-event behavior are shown. | Five paths yield descriptive ranges only; no uncertainty or population statistics are justified. | Results are useful evidence, but intentionally small and non-generalizing. |
| Figure/table quality | 4/5 | Workflow, representative path, hierarchy funnel, path observations, and configuration/evidence tables cover the story. | Figure 2 and Figure 4 are sparse; Figure 3 needs an especially clear explanation of Stage2 evaluation counts. | Good evidence coverage with layout and annotation refinements needed. |
| Writing quality | 4/5 | Scope is restrained and terminology is mostly consistent. | Some transitions are generic, and a few terms such as zero-event/zero-confirmation can be unified. | Clear and professional after targeted polishing. |
| Literature positioning | 4/5 | Nine verified references cover GNSS multipath, SAGE, GNSS-SDR, and GPS interface context. | The related-work gap is mostly embedded in the Introduction rather than made as a compact taxonomy. | Adequate literature foundation; stronger explicit gap framing would help. |
| Overall coherence | 4/5 | The story runs consistently from dynamic multipath to raw IQ, NAV-aided hierarchy, and Stage4 paths. | The method is more elaborate than the current result sample, creating a risk of perceived imbalance. | Coherent if the manuscript repeatedly labels the work as bounded path-level demonstration. |

## 4. Scientific story and contribution assessment

### 4.1 Story coherence

The scientific story is coherent:

```text
dynamic GNSS multipath
  -> receiver-level indicators do not expose individual paths
  -> real raw-IQ measurement enables path-level analysis
  -> NAV-aided SAGE supplies delay/Doppler path estimates
  -> hierarchical evidence avoids equating a local fit with a confirmed path
  -> bounded path-level observations are reported
```

The principal narrative risk is that the method can appear larger than the result set. The current manuscript already mitigates this by using “evaluated,” “bounded,” “descriptive,” and “future work,” and by including G18 as a valid zero-confirmation case. The final polish should make the demonstration scope even more explicit in the Abstract, Section IV-C, and Conclusion.

### 4.2 Novelty

The paper is sufficiently distinct if its contribution is framed as the integration and validation of a real dynamic GNSS measurement-to-path-evidence workflow. It is not defensible as a new SAGE estimator, a new optimization algorithm, or a completed channel model. The current sentence “This hierarchy is an operational evidence framework” is scientifically honest, but it also exposes the question a reviewer may ask: why should these successive evidence levels be trusted?

The existing evidence can support a clarification that temporal persistence and multi-snapshot joint estimation reduce the chance that an isolated correlation or local multi-component fit is treated as a retained path. This is a rationale for the hierarchy, not a claim of a measured false-positive rate.

### 4.3 Small-sample risk

The five confirmed paths across three primary contexts are the most important acceptance risk. It is not fatal if the paper consistently presents them as a bounded proof-of-pipeline/path-level demonstration and explicitly rejects environment-wide inference. It becomes problematic if “characterization” is read as a statistical or representative population claim. No new experiment is currently necessary for the present VTC scope; narrowing wording is the correct remedy.

### 4.4 NAV-aided clarity

The manuscript states that tracking information supplies synchronization/sample support, decoded navigation supplies PRN/time-aligned symbols for NAV wiping and window construction, and satellite-related information associates the PRN with the channel and valid interval. This is adequate at a high level. Because “NAV-aided” is prominent in the title/method, a compact input-to-operation sentence or table would remove ambiguity without adding data.

### 4.5 Stage4 scientific trust

The field-level confirmed rule is explicit and reproducible. A reviewer may nevertheless see `joint_valid`, `joint_multipath_count`, and `is_multipath` as software flags unless the manuscript adds one concise scientific explanation: approximately 100 ms of multi-snapshot joint estimation requires a candidate path to remain jointly supportable across snapshots, while the path-table condition prevents an intermediate model-order result from being promoted by label alone. The criterion remains an operational confirmation rule, not external ground truth.

## 5. Section-by-section review

| Section | Assessment | Recommended action |
|---|---|---|
| Abstract | Strong scope control; contains method, real measurement context, five-path result, zero-confirmation case, and limitations. | Keep. Add or retain an explicit bounded-demonstration phrase if space permits. |
| I. Introduction | Good problem-to-method progression and verified citations. | Add one compact research-gap sentence distinguishing receiver-level indicators from path-level evidence; do not claim an exhaustive literature gap. |
| II. Measurement and Experimental Setup | Hardware, signal, scenario contexts, and processing products are clear and evidence-backed. | Keep. State that time synchronization/front-end details are not documented rather than guessing them; keep LOW/MID/HIGH as contexts. |
| III. NAV-aided Hierarchical SAGE | Technically clear and careful about Stage2/Stage3 status. | Add one sentence on the scientific purpose of temporal persistence and joint confirmation; disclose the most important fixed parameters in compact form. |
| IV. Experimental Results | Correctly separates intermediate evidence, confirmed paths, zero-event output, and geometry limitation. | Tighten small-sample language and clarify the Stage2 annotation in Figure 3. |
| V. Conclusion | Does not claim a completed model or elevation law. | Keep the bounded conclusion; avoid adding any stronger “characterization” claim. |
| References | Current reference set is verified and compiled with zero BibTeX warnings. | Keep; no new references are required by this review unless the author later chooses to expand the related-work framing. |

## 6. Figure and table decisions

| Asset | Decision | Review action |
|---|---|---|
| Figure 1 workflow | **KEEP** | It gives the paper its end-to-end measurement-to-confirmed-path structure. Keep the current evidence boundary. |
| Figure 2 representative G25 path | **REVISE** | Retain the figure, but make direct versus secondary path identity and the absence of an unavailable Stage1 correlation curve unmistakable. No new curve should be fabricated. |
| Figure 3 hierarchical filtering | **KEEP with annotation revision** | Keep the funnel. Clarify that Stage2 L=1--4 values are model evaluations, not another unique-object count. |
| Figure 4 five path observations | **REVISE** | Retain only if the caption keeps “five observed paths; no fit or population inference.” If space is tight, a compact path-parameter table is a possible layout merge, not a new result. |
| Table I configuration | **KEEP** | It is valuable for reproducibility and uses confirmed source fields. |
| Table II evidence summary | **KEEP with compression** | Keep the four-case context and E/P counts, but avoid duplicating the full paragraph in the caption. |

## 7. Claim, terminology, and reproducibility scan

### 7.1 Abstract and Introduction

The Abstract has the required problem, measurement basis, method, bounded numerical result, and limitation. It does not claim a complete channel model or event-level elevation analysis. The Introduction uses established references and avoids absolute “first,” “novel,” or “no prior work” claims. The main improvement is to make the research gap more explicit without broadening it.

### 7.2 Experimental setup and geometry

The hardware and signal claims are supported by the measurement configuration evidence. Receiver model, antenna polarization/gain/mounting, GPS L1 C/A, 1575.42 MHz, 10.23 MHz, and interleaved little-endian signed-int16 IQ are included. IF, clock, trigger, and additional ADC facts are intentionally not asserted. Geometry is correctly described as partial, with NMEA/GSV-centered diagnostics and no event-level elevation release.

### 7.3 Stage semantics

The current manuscript is consistent on the critical distinctions:

- Stage0 defines valid windows; it does not label multipath.
- Stage1 produces candidates; candidate does not mean multipath.
- Stage2 `L\geq2` is model-order evidence; it does not mean confirmed multipath.
- Stage3 reliable centers are persistent intermediate evidence.
- Stage4 joint confirmation plus a valid multipath path-table row defines the confirmed set.

These distinctions must remain unchanged in any final polish.

### 7.4 Terminology risks

The manuscript should use one preferred operational phrase for the G18 case: “under the current Stage4 confirmation criterion, this task produced zero confirmed multipath events.” Do not replace it with “no multipath,” “LOS,” or “multipath-free.” Use “secondary path” or “additional component” consistently, and distinguish absolute carrier Doppler from relative path Doppler.

### 7.5 Reproducibility

The current paper discloses the 40-ms analysis window, approximately 100-ms joint interval, L=1--4, NAV-aided initialization, persistence checks, and output fields. Exact Stage1/Stage2 grids, all thresholds, and complete joint optimization details are not present in the five-page paper. This is a medium-level reproducibility limitation, not a reason to invent values. A compact parameter table or supplementary artifact reference would be the preferred remedy if the venue permits it.

### 7.6 Claim-risk scan

| Term or claim family | Current assessment | Required discipline |
|---|---|---|
| `novel`, `first` | No unsupported priority or first-of-kind claim is used as a scientific result. | Do not add priority language during polishing. |
| `significant`, `robust`, `accurate`, `effective` | Not used as unsupported performance claims for the five paths. | Prefer “observed,” “evaluated,” or “supported by the evidence.” |
| `demonstrate`, `validate`, `characterize` | Used in a bounded evaluation context; “characterization” is path-level/descriptive. | Keep the object and scope next to the verb; do not imply population validation. |
| `environment` | Refers to scenario-level context in the current evidence. | Do not turn context labels into causal environmental findings. |
| `elevation` | Explicitly limited by `PARTIAL` geometry alignment. | Do not add event-level elevation or LOW/MID/HIGH statistical claims. |
| `statistical`, `channel model` | Presented as future work or outside current scope. | Do not state that a model or database has been completed. |
| `multipath-free`, `LOS` | Not used to interpret G18 or Stage4 rejection. | Preserve operational zero-confirmation wording. |

The word “validation” is acceptable when it refers to pipeline/evidence validation under the stated criterion, but “evaluation” or “bounded demonstration” is safer for the five-path scientific result. The current manuscript generally follows this distinction.

## 8. Rejection-risk table

No issue is classified as Critical. The following issues are presentation or scope risks that can be addressed with the existing evidence.

| ID | Severity | Location | Issue | Why it matters | Recommended action | New experiment required? |
|---|---|---|---|---|---|---|
| H-01 | HIGH | Abstract, IV-C, V | Five confirmed paths may appear too small for unqualified “characterization.” | A reviewer may infer a population claim. | Repeatedly state bounded, descriptive, proof-of-pipeline scope. | No |
| H-02 | HIGH | II-D, III-B | NAV-aided role is distributed across paragraphs. | “NAV-aided” could be read as a label rather than an operational dependency. | Add a compact input-to-operation mapping. | No |
| H-03 | HIGH | III-C/D | Stage4 criterion is explicit but its scientific rationale is brief. | Software field names alone do not establish why joint confirmation is meaningful. | Explain persistence and multi-snapshot support without changing the criterion. | No |
| H-04 | HIGH | II-C, IV-D, V | Event-level geometry is partial. | Elevation/environment interpretations could be overread. | Keep context labels and explicitly exclude event-level elevation claims. | No |
| M-01 | MEDIUM | III, Table I | Exact search/tolerance details are incomplete. | Limits independent reproduction from the paper alone. | Add only the most consequential fixed settings or point to a reproducibility artifact. | No |
| M-02 | MEDIUM | I | Related-work gap is implicit. | Reviewer may not see the precise distinction from receiver-level indicators. | Add one restrained gap sentence using existing references. | No |
| M-03 | MEDIUM | Figure 2 | The representative path figure is sparse. | Its evidence value may be unclear without direct/secondary labels. | Improve annotation and caption; do not fabricate missing curves. | No |
| M-04 | MEDIUM | Figure 4 | Five points can look like a pseudo-statistical plot. | A reviewer may infer a distribution. | Make the no-fit/no-population caption prominent or merge into a compact table. | No |
| M-05 | MEDIUM | II-B | Time synchronization and some front-end details are undocumented. | Reproducibility questions may arise. | Mark them as unavailable; do not infer hardware facts. | No |
| M-06 | MEDIUM | Figure 3 | Stage2 annotation may be confused with a unique funnel count. | It could make the hierarchy look numerically inconsistent. | Label model evaluations separately and explicitly. | No |
| L-01 | LOW | Tables/captions | Some captions and paragraphs repeat the same boundary. | Uses scarce page space. | Compress duplicate wording while retaining the limitation. | No |
| L-02 | LOW | IV, V | “Zero-event” and “zero-confirmation” vary. | Minor terminology inconsistency. | Standardize to the operational zero-confirmation phrase. | No |
| L-03 | LOW | IV/Table II | Table II and surrounding text partly duplicate. | Reduces result density. | Keep the table; shorten surrounding repetition. | No |

**Issue count:** Critical 0; High 4; Medium 6; Low 3.

## 9. Top ten revision priorities

These are ordered by likely acceptance impact, not by implementation difficulty.

| Rank | Priority | Recommended change | Expected benefit | Risk if changed incorrectly |
|---:|---|---|---|---|
| 1 | Lock the claim boundary | State that the paper is a bounded path-level demonstration, not a general statistical characterization. | Prevents the five-path sample from being judged against a claim the paper does not make. | Over-weakening the contribution could make the paper sound like a mere software report. |
| 2 | Explain Stage4 scientifically | Add one sentence connecting multi-snapshot joint estimation to temporal/path consistency. | Makes the confirmation rule more than a list of implementation fields. | Do not imply measured false-positive performance or ground truth. |
| 3 | Make NAV dataflow explicit | Map tracking, telemetry, decoded NAV, RINEX/NMEA, and geometry diagnostics to their actual uses. | Improves method credibility and reproducibility. | Do not claim broadcast-ephemeris reconstruction or complete geometry. |
| 4 | Disclose critical fixed parameters | Retain 40 ms, approximately 100 ms, L=1--4, persistence, and relative-Doppler semantics in a compact table/sentence. | Gives reviewers enough scale to interpret the pipeline. | Do not invent undocumented grids or tolerances. |
| 5 | Tighten small-sample wording | Keep “five paths,” “descriptive,” and “no population inference” together wherever results are summarized. | Avoids overinterpretation of Figure 4 and path ranges. | Excessive caveats can bury the actual contribution. |
| 6 | Clarify Figure 3 | Separate Stage2 model evaluations from unique candidate/object counts in label and caption. | Removes an avoidable numerical confusion. | Do not change the underlying counts. |
| 7 | Revise Figure 2 annotation | Clearly identify direct/secondary positions and the unavailable correlation curve. | Makes the representative path evidence easier to audit. | Do not reconstruct a Stage1 curve from another artifact. |
| 8 | Decide Figure 4 layout | Retain as a five-point descriptive view or merge it into a compact path table if page pressure requires. | Preserves evidence while reducing pseudo-statistical appearance. | Do not add a fit, histogram, or distribution claim. |
| 9 | State the related-work gap plainly | Add a restrained sentence distinguishing receiver-level effects from path-level extraction. | Improves novelty/relevance framing without new citations. | Avoid absolute “first” or “no previous work” language. |
| 10 | Complete final submission gate | After author metadata and portal rules are known, run final PDF/IEEE compliance checks. | Removes administrative rather than scientific blockers. | Do not modify the scientific source merely to fill page space. |

## 10. Current decision on new experiments

**NEW_EXPERIMENT_CURRENTLY_REQUIRED = NO**

The current acceptance risks are primarily claim framing, Stage4 rationale, evidence-flow clarity, and layout. The frozen VTC evidence is sufficient for a bounded submission candidate. A future paper revision may need more paths or better geometry for stronger statistical claims, but that is not required to complete the present VTC candidate review and must not be represented as already available.

## 11. Source and status checks

- English manuscript source: `docs/vtc2027_spring/manuscript/latex/main.tex`; unchanged by this review.
- English Markdown draft: `docs/vtc2027_spring/manuscript/VTC2027_Spring_draft.md`; unchanged by this review.
- References: `docs/vtc2027_spring/manuscript/latex/references.bib`; unchanged and already verified.
- Candidate PDF: `docs/vtc2027_spring/submission/VTC2027_Spring_submission_candidate.pdf`; reviewed as existing evidence, not regenerated.
- Claim and reference audits: `claim_matrix_vtc_final_qa.csv` and `reference_verification_matrix.csv` support the bounded claims and citations.
- Figure/table provenance: `docs/vtc2027_spring/figures/figure_generation_manifest.json` supports the existing figures and tables.

The English source remains the only submission source. The companion Chinese file is for user review and translation assistance only; it is not a submission manuscript and is not independently maintained as a second scientific source.
