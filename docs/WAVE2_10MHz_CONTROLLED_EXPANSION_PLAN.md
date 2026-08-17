# Wave-2 10.23 MHz Controlled Expansion Plan

## 1. Scope and planning-only status

This document defines the next controlled SAGE expansion after the completed
Wave-A validation of G16, G25, and G12. It is a read-only planning artifact.
No MATLAB process, SAGE stage, batch executor, request generator, or scene
data operation was run while preparing it. No pipeline, metadata, inventory,
or existing result was changed.

The source snapshot is:

- inventory: `dataset/dataset_inventory.csv` (19 scene rows);
- dry-run plan: `dataset_generation_logs/batch_sage/batch_sage_dry_run_20260808T113454Z/batch_sage_plan.csv`;
- plan report: `dataset_generation_logs/batch_sage/batch_sage_dry_run_20260808T113454Z/batch_sage_plan_report.md`;
- current existing outputs: `scenes/**/sage_results/nav_sage_v2/**` plus protected
  `G06_nav_sage_v1`.

The dry-run plan predates the three Wave-A executions. Therefore the candidate
list below is a planning snapshot, not an execution authorization. Before any
request is created, the plan and output-absence checks must be regenerated or
repeated against the current filesystem.

## 2. Filtering result

The filtering was applied at scene-PRN task level:

1. `sample_rate_hz` must be exactly `10230000` (10.23 MHz).
2. `scene_id` must not be `F1023_V70_D0117_P2`.
3. The plan row must be `ready` with `preflight_status=pass`.
4. Channel resolution must be `unique`; manual channel-selection rows are
   excluded.
5. The tracking, telemetry, raw-IQ, RINEX NAV, trajectory, and both satellite
   geometry inputs must pass the plan preflight.
6. The exact task output directory must not currently exist.

| Filter stage | Task count |
|---|---:|
| All dry-run tasks | 124 |
| 10.23 MHz tasks | 83 |
| Reference-scene tasks removed | 7 |
| 10.23 MHz blocked tasks removed | 12 |
| Of the blocked tasks, unresolved multi-channel tasks | 5 |
| 10.23 MHz tasks ready before current-output exclusion | 64 |
| Newly existing non-reference Wave-A outputs removed | 3 |
| Final new-task candidate pool | **61** |
| Candidate scenes | **12** |

The three existing non-reference outputs removed from the ready queue are
`F1023_V70_D0120_P7/G16`, `F1023_v50_D0127_P1/G25`, and
`F1023_V70_D0122_P1/G12`. The six completed reference-scene `nav_sage_v2`
outputs and protected `G06_nav_sage_v1` are excluded independently by the
reference-scene rule.

All 61 candidates have a unique inventory channel, 10.23 MHz support, and a
currently absent task-specific output path in the planning scan. Their common
plan estimate is 1,175 typical 40 ms windows, 97 typical Stage2 candidates,
and 388 typical Stage2 model evaluations. The estimate confidence is low:
the plan explicitly labels it `window_estimate_reference_prior`; it is not an
observed Stage0 count for these scenes.

## 3. Recommended Wave-2 execution order

To maximize scene coverage, the first tranche contains one task from five
scenes with no completed Wave-A result. These five should be reviewed as
individual immutable requests and executed serially. The next tranche adds
four more previously untested scenes. Only after those scene-level checks
should the plan return to PRN extensions in scenes already represented by
Wave-A.

### Wave-2A: first controlled tranche

| Order | Scene | PRN | Channel | Sampling rate | Plan estimate | Risk / reason |
|---:|---|---|---:|---:|---|---|
| 1 | `F1023_V120_D0121_P2` | G11 | 0 | 10.23 MHz | 1175 windows; 97 Stage2 candidates; 388 fits | `R1-LARGE-RAW`: unique channel and complete preflight, but external raw path is about 24.61 GB and the window prior is low-confidence |
| 2 | `F1023_V70_D0117_P4` | G12 | 4 | 10.23 MHz | 1175; 97; 388 | `R1`: new scene, unique channel, complete input preflight, output absent; only the reference-prior estimate warning |
| 3 | `F1023_V70_D0120_P1` | G18 | 2 | 10.23 MHz | 1175; 97; 388 | `R1`: new scene and unique channel; no blocked input or namespace collision |
| 4 | `F1023_V70_D0120_P5` | G23 | 0 | 10.23 MHz | 1175; 97; 388 | `R1`: new scene and unique channel; no blocked input or namespace collision |
| 5 | `F1023_V80_D0117_P8` | G31 | 1 | 10.23 MHz | 1175; 97; 388 | `R1`: new scene and unique channel; the unrelated blocked G29 mapping is not part of this task |

The first tranche deliberately uses five different scenes and five different
PRNs. No physical LOS/multipath ranking is asserted: the current plan does
not provide a validated cross-scene elevation/CN0/environment ranking for
these choices.

### Wave-2B: coverage completion and controlled scene extensions

| Order | Scene | PRN | Channel | Sampling rate | Plan estimate | Risk / reason |
|---:|---|---|---:|---:|---|---|
| 6 | `F1023_V70_D0120_P8` | G16 | 4 | 10.23 MHz | 1175; 97; 388 | `R1`: new scene, unique channel, complete preflight, output absent |
| 7 | `F1023_V70_D0120_P9` | G05 | 10 | 10.23 MHz | 1175; 97; 388 | `R1`: new scene and unique channel; the blocked G23/G28 rows are excluded |
| 8 | `F1023_V70_D0122_P2` | G15 | 8 | 10.23 MHz | 1175; 97; 388 | `R1`: new scene and unique channel; blocked geometry rows are excluded |
| 9 | `F1023_v90_D0117_P7` | G11 | 6 | 10.23 MHz | 1175; 97; 388 | `R1`: new scene and unique channel, with output absent |
| 10 | `F1023_V70_D0120_P7` | G18 | 4 | 10.23 MHz | 1175; 97; 388 | `R2`: task output is absent, but the scene already has the Wave-A G16 result; maintain exact namespace isolation |
| 11 | `F1023_v50_D0127_P1` | G11 | 10 | 10.23 MHz | 1175; 97; 388 | `R2`: task output is absent, but the scene already has Wave-A G25; do not touch G25 |
| 12 | `F1023_V70_D0122_P1` | G13 | 5 | 10.23 MHz | 1175; 97; 388 | `R2`: task output is absent, but the scene already has Wave-A G12; do not touch G12 |

Wave-2A and Wave-2B together provide one operationally simple candidate per
eligible scene. They are a recommended order, not an authorization to create
all twelve requests at once.

Risk codes:

- `R1`: new scene coverage; current plan says all required inputs pass and the
  channel is unique. The main uncertainty is the low-confidence workload prior.
- `R1-LARGE-RAW`: same as R1, with an unusually large external raw-IQ path;
  confirm path availability and read permissions again at preflight.
- `R2`: the specific PRN output is new, but the scene already has a Wave-A
  result. This is safe only if the exact PRN namespace and existing outputs are
  rechecked before execution.

## 4. Complete 61-task candidate pool

The following table is the complete new-task pool after the requested
exclusions. Every row is 10.23 MHz. `A` and `B` identify the recommended
tranches above; `R` is a reserve candidate, not selected for the first
controlled tranche. All rows use the common low-confidence estimate stated in
Section 2.

| Scene | PRN | Channel | Rate | Priority | Risk |
|---|---|---:|---:|---|---|
| `F1023_V120_D0121_P2` | G11 | 0 | 10.23 MHz | A | R1-LARGE-RAW |
| `F1023_V120_D0121_P2` | G24 | 2 | 10.23 MHz | R | R1-LARGE-RAW |
| `F1023_V120_D0121_P2` | G25 | 5 | 10.23 MHz | R | R1-LARGE-RAW |
| `F1023_V120_D0121_P2` | G28 | 6 | 10.23 MHz | R | R1-LARGE-RAW |
| `F1023_V120_D0121_P2` | G32 | 7 | 10.23 MHz | R | R1-LARGE-RAW |
| `F1023_v50_D0127_P1` | G11 | 10 | 10.23 MHz | B | R2 |
| `F1023_v50_D0127_P1` | G28 | 4 | 10.23 MHz | R | R2 |
| `F1023_v50_D0127_P1` | G29 | 9 | 10.23 MHz | R | R2 |
| `F1023_v50_D0127_P1` | G31 | 5 | 10.23 MHz | R | R2 |
| `F1023_V70_D0117_P4` | G11 | 2 | 10.23 MHz | R | R1 |
| `F1023_V70_D0117_P4` | G12 | 4 | 10.23 MHz | A | R1 |
| `F1023_V70_D0117_P4` | G25 | 7 | 10.23 MHz | R | R1 |
| `F1023_V70_D0117_P4` | G28 | 6 | 10.23 MHz | R | R1 |
| `F1023_V70_D0117_P4` | G29 | 9 | 10.23 MHz | R | R1 |
| `F1023_V70_D0117_P4` | G32 | 3 | 10.23 MHz | R | R1 |
| `F1023_V70_D0120_P1` | G18 | 2 | 10.23 MHz | A | R1 |
| `F1023_V70_D0120_P1` | G26 | 3 | 10.23 MHz | R | R1 |
| `F1023_V70_D0120_P1` | G27 | 8 | 10.23 MHz | R | R1 |
| `F1023_V70_D0120_P1` | G29 | 5 | 10.23 MHz | R | R1 |
| `F1023_V70_D0120_P1` | G31 | 9 | 10.23 MHz | R | R1 |
| `F1023_V70_D0120_P5` | G16 | 1 | 10.23 MHz | R | R1 |
| `F1023_V70_D0120_P5` | G18 | 2 | 10.23 MHz | R | R1 |
| `F1023_V70_D0120_P5` | G23 | 0 | 10.23 MHz | A | R1 |
| `F1023_V70_D0120_P5` | G26 | 7 | 10.23 MHz | R | R1 |
| `F1023_V70_D0120_P5` | G27 | 10 | 10.23 MHz | R | R1 |
| `F1023_V70_D0120_P7` | G18 | 4 | 10.23 MHz | B | R2 |
| `F1023_V70_D0120_P7` | G26 | 6 | 10.23 MHz | R | R2 |
| `F1023_V70_D0120_P7` | G31 | 8 | 10.23 MHz | R | R2 |
| `F1023_V70_D0120_P8` | G16 | 4 | 10.23 MHz | B | R1 |
| `F1023_V70_D0120_P8` | G18 | 9 | 10.23 MHz | R | R1 |
| `F1023_V70_D0120_P8` | G23 | 11 | 10.23 MHz | R | R1 |
| `F1023_V70_D0120_P8` | G26 | 3 | 10.23 MHz | R | R1 |
| `F1023_V70_D0120_P9` | G05 | 10 | 10.23 MHz | B | R1 |
| `F1023_V70_D0120_P9` | G16 | 9 | 10.23 MHz | R | R1 |
| `F1023_V70_D0120_P9` | G18 | 1 | 10.23 MHz | R | R1 |
| `F1023_V70_D0120_P9` | G26 | 6 | 10.23 MHz | R | R1 |
| `F1023_V70_D0120_P9` | G27 | 5 | 10.23 MHz | R | R1 |
| `F1023_V70_D0120_P9` | G29 | 4 | 10.23 MHz | R | R1 |
| `F1023_V70_D0120_P9` | G31 | 7 | 10.23 MHz | R | R1 |
| `F1023_V70_D0122_P1` | G13 | 5 | 10.23 MHz | B | R2 |
| `F1023_V70_D0122_P1` | G14 | 9 | 10.23 MHz | R | R2 |
| `F1023_V70_D0122_P1` | G15 | 8 | 10.23 MHz | R | R2 |
| `F1023_V70_D0122_P1` | G17 | 2 | 10.23 MHz | R | R2 |
| `F1023_V70_D0122_P1` | G19 | 11 | 10.23 MHz | R | R2 |
| `F1023_V70_D0122_P1` | G22 | 4 | 10.23 MHz | R | R2 |
| `F1023_V70_D0122_P1` | G24 | 7 | 10.23 MHz | R | R2 |
| `F1023_V70_D0122_P2` | G15 | 8 | 10.23 MHz | B | R1 |
| `F1023_V70_D0122_P2` | G19 | 11 | 10.23 MHz | R | R1 |
| `F1023_V70_D0122_P2` | G23 | 10 | 10.23 MHz | R | R1 |
| `F1023_V70_D0122_P2` | G24 | 3 | 10.23 MHz | R | R1 |
| `F1023_V80_D0117_P8` | G12 | 4 | 10.23 MHz | R | R1 |
| `F1023_V80_D0117_P8` | G25 | 10 | 10.23 MHz | R | R1 |
| `F1023_V80_D0117_P8` | G28 | 6 | 10.23 MHz | R | R1 |
| `F1023_V80_D0117_P8` | G31 | 1 | 10.23 MHz | A | R1 |
| `F1023_V80_D0117_P8` | G32 | 11 | 10.23 MHz | R | R1 |
| `F1023_v90_D0117_P7` | G11 | 6 | 10.23 MHz | B | R1 |
| `F1023_v90_D0117_P7` | G12 | 10 | 10.23 MHz | R | R1 |
| `F1023_v90_D0117_P7` | G25 | 0 | 10.23 MHz | R | R1 |
| `F1023_v90_D0117_P7` | G28 | 4 | 10.23 MHz | R | R1 |
| `F1023_v90_D0117_P7` | G29 | 11 | 10.23 MHz | R | R1 |
| `F1023_v90_D0117_P7` | G32 | 5 | 10.23 MHz | R | R1 |

The table intentionally does not include any blocked, ambiguous-channel,
reference-scene, or already existing task.

## 5. Required next-step controls

Before Wave-2A is released for execution:

- regenerate or revalidate the batch plan so the three Wave-A outputs are
  represented as existing and cannot be selected again;
- re-read `dataset_inventory.csv` and confirm the exact PRN-to-channel mapping
  and uniqueness for each approved row;
- confirm raw IQ, tracking MAT, telemetry DAT, RINEX NAV, NMEA trajectory, and
  both satellite geometry CSVs exist and are non-empty;
- confirm the exact `scenes/<scene>/sage_results/nav_sage_v2/<PRN>` output is
  absent, while unrelated results remain untouched;
- produce one immutable request per task, with no hidden reserve tasks and no
  resume/overwrite mode;
- use the normal-user `TJ-CHANNEL\\Jing_` PowerShell 7 wrapper, validation-only
  first, MATLAB smoke marker plus exit `0`, then serial `-Execute`;
- run independent QA after every task and stop release progression if MATLAB
  smoke, executor status, output completeness, or isolation fails.

No request manifest, selected-task CSV, or execution command is generated by
this planning report. The next safe action is a separate human review of the
five Wave-2A rows followed by a fresh validation-only pass.

## Current Status

Wave-A 10.23 MHz validation is closed with G16, G25, and G12 PASS. The current
Wave-2 planning pool contains 61 eligible new scene-PRN tasks across 12
scenes. The recommended first action is Wave-2A's five cross-scene tasks;
do not start an unrestricted batch and do not include any 20.46 MHz task.
