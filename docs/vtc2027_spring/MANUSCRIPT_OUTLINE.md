# VTC2027-Spring Five-Page Manuscript Outline

The following budget is a writing target, not a statement that all sections are complete.

The submission-format audit is recorded in `submission/SUBMISSION_REQUIREMENTS.md`. The intended class is the generic official IEEE conference class in conference mode; the VTC-specific package, author metadata, final references, and compiled page count remain pending.

| Section | Target space | Objective | Current source/status |
|---|---:|---|---|
| I. Introduction | 0.6 page | Dynamic vehicular GNSS multipath, receiver-level indicator limits, need for path-level measurements | `docs/paper_draft/sections/01_Introduction.md`; draft asset |
| II. Measurement and Processing Framework | 0.9–1.0 page | RF measurement, GNSS-SDR support, NAV-aided observation construction, data provenance | `04_Experimental_Setup.md`, `03_Methodology.md`; draft asset |
| III. Hierarchical SAGE Multipath Extraction | 1.0–1.1 pages | Stage0–Stage4 evidence hierarchy and confirmed criterion | `03_Methodology.md`, `05_Pipeline_Validation.md`; draft asset |
| IV. Experimental Results | 1.8–2.0 pages | Validation funnel, representative path case, bounded path characterization, limited environment/elevation observations | QA reports and evidence matrix; aggregate figures pending |
| V. Conclusion | 0.25–0.3 page | What the measurement-based extraction demonstrates and what remains open | `07_Conclusion.md`; final wording pending |
| References | Venue-dependent | Focused related work and SAGE/GNSS/channel-model references | Literature completion pending |

## Section plan

### I. Introduction

Motivate dynamic multipath as a time-varying propagation process rather than only a receiver-performance error. Position SAGE as a high-resolution path extraction tool and state the bounded VTC contribution.

### II. Measurement and Processing Framework

Describe GPS L1 C/A raw IQ, RF-Catcher V2, roof-mounted RHCP antenna, GNSS-SDR tracking/telemetry/navigation support, trajectory and geometry provenance. Keep time synchronization details marked as undocumented.

### III. Hierarchical SAGE Multipath Extraction

Present the signal model and Stage0–Stage4 logic. Explicitly state that Stage1 candidates, Stage2 `L>=2`, and Stage3 reliable centers are intermediate evidence. Only Stage4 joint confirmation enters the confirmed event/path set.

### IV. Experimental Results

1. **Hierarchical filtering:** Stage0-to-Stage4 funnel for reference and selected validated tasks.
2. **Representative confirmed case:** one existing confirmed event/path case with delay, relative Doppler, power, and confirmation context.
3. **Path-level characterization:** empirical path-level observations if aggregation and denominators pass QA.
4. **Elevation/environment observations:** only bounded LOW/MID/HIGH and scene-class comparisons supported by window-level geometry QA.
5. **Negative/limitation note:** long-record runtime and raw-coarse v3 posterior coverage failure, without presenting v3 as production.

### V. Conclusion

Conclude only what the validated measurement chain and hierarchical path confirmation establish. Defer complete channel statistical modeling and database completion to future work.

## Writing constraints

- Use “under the current Stage4 confirmation criterion” for zero-event cases.
- Do not write “no physical multipath” for G18, G16, G25, or any zero-event case.
- Do not call Stage2 high-order models or Stage3 reliable centers confirmed paths.
- Do not claim all scenes are processed or that a statistical model is complete.
- Keep G16’s execution-policy caveat concise and factual; do not turn the paper into an executor bug report.
