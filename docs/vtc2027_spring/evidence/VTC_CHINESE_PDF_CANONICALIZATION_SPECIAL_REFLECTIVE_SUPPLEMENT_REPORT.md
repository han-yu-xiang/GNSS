# VTC Chinese Review PDF Canonicalization + Special Reflective Supplement Report

Date: 2026-08-17

## Part A — Chinese review PDF

The current `main_cn_review.tex` was rebuilt in its own directory with the required `xelatex -> bibtex -> xelatex -> xelatex` chain. All four commands exited with code `0`.

| Gate | Result |
|---|---|
| Canonical Chinese PDF | `docs/vtc2027_spring/manuscript/latex_cn_review/main_cn_review.pdf` |
| Current source SHA-256 | `EBE10DAD07C6B58EE7528F96855EF8CBBFF20CE46361C7576189D9D95EC680E2` |
| Canonical PDF SHA-256 | `32F79236D6EB72466CF85CD5F92EDD9E42814E9F676189CEA88E8F0643400A90` |
| Page count | `4` |
| File size | `369539` bytes |
| Compile timestamp | `2026-08-17 00:21:42` local time |
| Temporary versioned PDF remaining | `NO` |
| Chinese canonical only | `YES` |
| Figure 1 rendered | `YES` |
| Figure 2 rendered | `YES` |
| Figure 3 rendered | `YES` |
| Figure 4 rendered | `YES` |
| Table 1 rendered | `YES` |
| Table 2 rendered | `YES` |
| References rendered | `YES` |
| Missing glyphs | `NO` |

The obsolete `main_cn_review_audit_20260816.pdf` was removed only after the new canonical PDF compiled, opened, rendered, and had its hash recorded. No source, figure, reference, English submission PDF, evidence artifact, or production artifact was removed. The canonical review PDF is review-only; the English `main.tex` remains the submission source of truth.

## Part B — Current Special Reflective coverage

The current 10.23 MHz metadata census contains two Special Reflective scenes:

- `F1023_V70_D0120_P9`: the existing Tier A+B scene, represented by the QA-passed `G05/ch10` task with 2 confirmed events and 2 confirmed paths.
- `F1023_V70_D0122_P2`: an independent Special Reflective scene not yet represented in the current Tier A+B environment comparison.

Therefore:

```text
TOTAL_SPECIAL_REFLECTIVE_SCENES = 2
CURRENT_TIER_AB_SCENES = 1
UNREPRESENTED_SCENES = F1023_V70_D0122_P2
```

No Highway/Open, Urban, or Mountain/Valley supplement was selected in this round.

## Selected supplemental task

| Field | Value |
|---|---|
| Scene | `F1023_V70_D0122_P2` |
| PRN | `G15` |
| Tracking channel | `ch8` |
| Sampling rate | `10.23 MHz` |
| Environment | `Special Reflective` |
| Raw metadata size | `5097652736` bytes; raw content not opened |
| Cost class | `MEDIUM` metadata/raw-size proxy; exact Stage0 workload and runtime remain unknown until execution |
| Selection state | Single-channel, nonblocked, source-plan `ready`, input provenance present, output absent |
| Selection reason | Independent scene coverage and current production validity; not a prediction of multipath outcome |

The task was selected because it adds an independent Special Reflective scene while satisfying the current production input and namespace gates. No low elevation, reflection strength, expected multipath, expected path count, or other positive-outcome prediction was used.

## Comparability

`TIER_AB_PARAMETER_COMPARABILITY = PASS`

The comparison uses the same 10.23 MHz scope, current pipeline/executor/wrapper contract, compatible SAGE estimator and Stage4 confirmation semantics, and the existing definitions of delay, tracking-relative Doppler, relative power, and coherence. Geometry remains a scene/provenance aid rather than an event-level elevation claim; P2 records NMEA/GSV geometry provenance and RINEX NAV PRN filtering without broadcast-ephemeris position recomputation.

## Execution status

```text
SPECIAL_REFLECTIVE_TASK_SELECTED = YES
REQUEST_CREATED = YES
PREFLIGHT_PASS = YES
SAGE_EXECUTED = NO
AUTO_CONTINUATION = NO
```

Immutable request:

`dataset_generation_logs/batch_sage_execution_requests/vtc_special_reflective_supplement_p2_g15_20260817/execution_request.json`

Request SHA-256:

`0d8de5948101f67bfc9458785d40f876412617b2fd903d695aab2cb85abd85a5`

Preflight record:

`dataset_generation_logs/batch_sage_execution_requests/vtc_special_reflective_supplement_p2_g15_20260817/preflight_report.md`

Python-only dry-run:

`dataset_generation_logs/batch_sage_execution/batch_sage_execution_20260816T163442Z/`

The dry-run accepted exactly one row, rejected zero rows, did not invoke MATLAB, and previewed `Resume=false`. The human-only Execute command is recorded in the preflight report; it was not run in this task because Codex cannot safely launch the required normal-user MATLAB environment.

## If execution completed

Not applicable. There is no new Special Reflective event/path result, independent QA result, or updated census from this preparation task.

```text
QA_STATUS = NOT_RUN
N_SCENES = NOT_UPDATED
N_TASKS = NOT_UPDATED
N_EVENTS = NOT_UPDATED
N_PATHS = NOT_UPDATED
```

## Paper decision

`SPECIAL_REFLECTIVE_PAPER_DECISION = PENDING / NOT DECIDED`

The decision cannot be selected before the second independent scene is executed and independently QA-passed. It must be based on coverage, independent-scene replication, confirmed-path parameter availability, and scientific interpretability—not on whether the eventual parameter values look favorable or match an expected trend. Current paper environment conclusions and Figure 4 were not changed.

## Figure 4 proposal

`CURRENT_FIGURE_MODIFIED = NO`

After a future QA-passed result, prepare a proposal only:

- if the second scene supplies enough independent confirmed-path evidence, retain a four-environment descriptive panel and annotate the updated Special Reflective path sample size;
- if it supplies a usable case but not enough cross-scene replication, consider a three-environment main comparison and a separate Special Reflective case-only panel;
- if it adds no sufficient independent path-parameter evidence, consider the three-environment comparison only, with the decision justified by insufficient replication rather than an undesired parameter difference.

No formal figure was redrawn in this task.

## Final flags

```text
CHINESE_CANONICAL_ONLY = YES
SPECIAL_REFLECTIVE_SECOND_SCENE_TARGETED = YES
HIGHWAY_SUPPLEMENT_EXECUTED = NO
AUTO_CONTINUATION = NO
NEXT_VTC_DECISION_REQUIRED = YES
```

No experiment was executed:

- raw IQ content read: no;
- MATLAB: no;
- SAGE: no;
- batch production execution: no;
- existing production artifact modified: no.
