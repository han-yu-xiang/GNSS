# SAGE-Based Path Extraction and Statistical GNSS Multipath Channel Modeling

## Working title

SAGE-Based Path Extraction and Environment-Conditioned Statistical GNSS Multipath Channel Modeling from Vehicle-Mounted Raw IQ Measurements

## Research positioning

The paper is positioned as a path-extraction and channel-modeling study, rather than only a receiver-level GNSS multipath characterization study. The central contribution is the traceable conversion of raw GNSS measurements into path-level parameters and, after sufficient multi-scene production, environment-conditioned statistical channel parameters.

The current research objective is:

```text
Raw GNSS IQ
    -> GNSS-SDR tracking/navigation support
    -> SAGE multipath path extraction
    -> path-level parameters
       (delay, Doppler, power, phase)
    -> channel parameter derivation
       (PDP, RMS delay spread, Doppler spread, K-factor)
    -> environment-conditioned statistical GNSS multipath channel model
```

## Paper status

- This directory is a writing framework, not a completed manuscript.
- The 10.23 MHz full-SAGE production line has started.
- The first production task, `F1023_V70_D0117_P4/G11/ch2`, has passed QA.
- `F1023_V70_D0120_P1/G18/ch2` is running according to the current project status; no result is written here until independently verified.
- The raw-coarse v3 acceleration experiment is retained as a frozen negative result and must not be presented as a production selector.
- Statistical-model results, complete event-database totals, and all-scene conclusions remain placeholders until the corresponding experiments and QA are complete.

## Manuscript structure

1. Introduction
2. Related Work
3. Methodology
4. Experimental Setup
5. Pipeline Validation
6. Results
7. Conclusion

## Chapter planning

### Chapter 1 — Introduction

- Dynamic GNSS multipath in vehicle-mounted measurements.
- The need for statistical channel modeling rather than only isolated event descriptions.
- Limitations of receiver-level indicators when path-level delay, Doppler and power behavior are required.

### Chapter 2 — Related Work

- 2.1 GNSS multipath characterization.
- 2.2 High-resolution multipath parameter estimation.
- 2.3 Statistical wireless channel modeling.

### Chapter 3 — Methodology

- 3.1 End-to-end GNSS multipath processing framework.
- 3.2 SAGE-based multipath path extraction.
- 3.3 Path-level parameter to channel-parameter conversion:
  - Power Delay Profile (PDP).
  - RMS delay spread.
  - Doppler spread.
  - Ricean K-factor.
- 3.4 Environment-conditioned statistical modeling.

### Chapter 4 — Experimental Setup

- RF-Catcher measurement system.
- GPS L1 C/A signal.
- 10.23 MHz production dataset.
- 13 measurement scenes.
- Human-confirmed environment metadata.

### Chapter 5 — Pipeline Validation

- Production pipeline validation and reproducibility controls.
- Reference and Wave-A validation context.
- G11 completed production validation.
- G18 validation status only after its independent QA is complete.

### Chapter 6 — Results

- 6.1 Dataset overview.
- 6.2 Multipath occurrence statistics.
- 6.3 Delay characteristics: excess delay and RMS delay spread.
- 6.4 Doppler characteristics: Doppler shift and Doppler spread.
- 6.5 Power characteristics: PDP and K-factor.
- 6.6 Environment-dependent channel modeling.

This chapter remains a controlled placeholder for quantities not yet supported by completed production and QA artifacts.

### Chapter 7 — Conclusion

Emphasize the eventual dynamic GNSS multipath statistical channel model, while separating completed evidence from planned database construction and model generation.

## Evidence rule

Every numerical result in the manuscript must trace to a project artifact, execution receipt, QA report, or immutable provenance record. Planned work must be labelled as planned or pending; it must not be written as an observed result.

## Core production chain

```text
raw IQ
  -> GNSS-SDR outputs
  -> Stage0 NAV/window preparation
  -> Stage1 NAV-aided fast scan
  -> Stage2 fractional SAGE L=1..4
  -> Stage3 persistence/reliable centers
-> Stage4 joint 100 ms confirmation
  -> path-level parameter database
  -> channel-parameter database
  -> environment-conditioned statistical GNSS channel model
```

The event/path and channel databases are planned outputs. They are not currently claimed as completed.

## Current writing priorities

- Establish the measurement and processing methodology from already validated artifacts.
- Document reference, Wave-A, Wave-2A, and first-production QA facts without extending their scope.
- Keep the 10.23 MHz production results section as a controlled placeholder until more tasks pass post-run QA.
- Describe raw-coarse v3 as a reproducibility-preserving acceleration investigation with a negative posterior coverage result.
- Build the paper around path-level delay, Doppler, power and phase extraction.
- Derive PDP, RMS delay spread, Doppler spread and K-factor only after the relevant path database is complete and QA-checked.
- Defer statistical conclusions until coverage-complete multi-scene data, path ingestion and channel-parameter derivation exist.

## Database roadmap

```text
scene
  -> extracted path
  -> derived channel parameter
```

- Scene metadata layer: established for the 13-scene 10.23 MHz production scope.
- Path database: planned, not started/completed.
- Channel-parameter database: planned, not started/completed.
