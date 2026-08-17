# 10 MHz Full-SAGE Production Execution Plan v1

Status: Planned / Not started. This is a planning manifest and execution design only; it is not an execution request and contains no approval to launch SAGE.

## 1. Scope and safety boundary

- Production route: raw IQ -> GNSS-SDR outputs -> Stage0 -> Stage1 -> Stage2 -> Stage3 -> Stage4 -> confirmed event/path database.
- Scope is only 10.23 MHz (10230000 Hz). 20.46 MHz is excluded.
- The manifest includes only input-ready, unique-channel, not-started tasks. Existing completed outputs and blocked tasks are explicitly excluded.
- Raw IQ was not opened; raw fields are metadata/path/size provenance only. No raw content hash was recomputed.
- No MATLAB, SAGE, batch executor, or execution request was run or generated.

## 2. Manifest

- File: `dataset_generation_logs/production_planning_10mhz_20260812/production_task_manifest_10MHz_v1.json`
- Schema: `production-task-manifest-10MHz-1`
- Task count: 67 (83 inventory tasks minus 11 completed and 5 blocked).
- Source inventory SHA-256: `af368feba90797584d7690d4927ed32de604651a5a62662f4adce348a89e4bb4`.
- Each entry freezes scene, PRN, one inventory-confirmed channel, sample rate, raw/GNSS-SDR/NAV/trajectory/geometry provenance, expected output namespace, `new_only=true`, `resume_allowed=false`, and `planned_not_started` status.
- `estimated_complexity_class` is deliberately `unknown_until_Stage0`; no unobserved runtime or window count is fabricated.

## 3. Blocked multi-channel audit

| Scene | PRN | Available channels | Tracking evidence | Telemetry evidence | Recommendation | Reason |
|---|---|---|---|---|---|---|
| F1023_V120_D0121_P2 | G06 | 6;9 | ch6:present;ch9:present | ch6:present;ch9:present | Remain blocked; no automatic choice | Both/all candidates exist; current metadata does not establish a unique scientific channel for this PRN |
| F1023_V120_D0121_P2 | G12 | 5;11 | ch5:present;ch11:present | ch5:present;ch11:present | Remain blocked; no automatic choice | Both/all candidates exist; current metadata does not establish a unique scientific channel for this PRN |
| F1023_V120_D0121_P2 | G19 | 0;1;3 | ch0:present;ch1:present;ch3:present | ch0:present;ch1:present;ch3:present | Remain blocked; no automatic choice | Both/all candidates exist; current metadata does not establish a unique scientific channel for this PRN |
| F1023_V120_D0121_P2 | G29 | 3;10 | ch3:present;ch10:present | ch3:present;ch10:present | Remain blocked; no automatic choice | Both/all candidates exist; current metadata does not establish a unique scientific channel for this PRN |
| F1023_V70_D0120_P9 | G23 | 3;10 | ch3:present;ch10:present | ch3:present;ch10:present | Remain blocked; no automatic choice | Both/all candidates exist; current metadata does not establish a unique scientific channel for this PRN |

The audit confirms candidate files exist for every listed channel, but file existence alone does not prove which tracking channel should represent the PRN. No recommendation is made without a human-reviewed channel-selection rule or additional provenance. These tasks are excluded from v1 rather than guessed.

## 4. Batch grouping

| Batch | Role | Included task policy | Historical complexity basis |
|---|---|---|---|
| Batch A | Pipeline validation batch | First unique-channel task from each not-yet-represented scene; serial execution and independent QA. | Wave-A observed 45-65 min for roughly 1,600-2,400 windows; actual new tasks remain unknown until Stage0. |
| Batch B | Main production batch | After Batch A QA, expand unique-channel tasks by scene coverage, then additional PRNs. | Use actual Stage0 window count; do not extrapolate from raw size. |
| Batch C | Long-running tasks | F1023_V120_D0121_P2 remaining unique tasks after a reviewed long-task pilot; blocked multi-channel tasks remain out. | Existing G11: 15,210 windows, Stage1 about 8.1 h, Stage2 about 11.4 h, total about 19.6 h. |

Suggested Batch A order (planned only): `F1023_V70_D0117_P4/G11/ch2`, `F1023_V70_D0120_P1/G18/ch2`, `F1023_V70_D0120_P5/G16/ch1`, `F1023_V70_D0120_P8/G16/ch4`, `F1023_V70_D0120_P9/G05/ch10`, `F1023_V70_D0122_P2/G10/ch6`, `F1023_V80_D0117_P8/G12/ch4`, `F1023_v90_D0117_P7/G11/ch6`. The manifest contains all eligible tasks; this order is only a review priority, not a selected execution list. Remaining tasks in Wave-A scenes are Batch B, not Batch A.

## 5. Recommended execution order

1. Complete a preflight-only review of the first Batch A task and create a separate immutable execution request only when human approval is obtained.
2. Execute one task serially under the normal Windows user wrapper, then complete independent QA before approving the next task.
3. Prefer new scene coverage before many PRNs from one scene.
4. Schedule long-scene Batch C only with an explicit multi-hour window, disk-space check, progress monitoring, and manual interruption policy.
5. Resolve blocked channel mappings in a separate metadata/provenance review; do not add them to the manifest until a single channel is explicitly frozen.

## 6. Checkpoint and failure recovery

- Preflight: inventory/metadata hash, unique channel, 10.23 MHz, input paths, Stage0 prerequisite policy, output absence, protected namespaces, pipeline hash, disk space, and normal-user MATLAB environment.
- Execution: one task at a time; capture start/end UTC, Python/MATLAB return codes, stdout/stderr, progress, checkpoint, output file list and hashes.
- Interruption/failure: preserve all partial outputs and receipts; mark interrupted/failed; do not delete, silently resume, or interpret partial stages as science.
- Recovery: new immutable request/output namespace or separately approved resume policy; no automatic retry and no automatic continuation to another task.
- Completed zero-event Stage4 is valid only when all Stage0-Stage4 files and QA checks pass.

## 7. Event/path database preparation

Create a separate versioned ingest namespace, not under `scenes/**/sage_results`, with normalized `run`, `window`, `candidate`, `confirmed_event`, and `path` tables. Store source namespace, task manifest SHA, stage file hashes, channel/sample-rate provenance, geometry provenance, and QA status on every record. Use `joint_valid=1` plus `joint_multipath_count>0` as the current confirmed criterion. Preserve `confirmed_multipath`, `rejected_candidate`, and `los_reference` as explicit labels; incomplete or unscanned windows must not become LOS negatives.

## 8. Current blockers

- Five multi-channel tasks remain excluded: four in `F1023_V120_D0121_P2` and one in `F1023_V70_D0120_P9`.
- Stage0 window counts for all new tasks are unknown until a task-specific Stage0 artifact exists; manifest complexity remains unknown.
- Geometry is an existing NMEA GSV-based product with RINEX NAV PRN filtering, not a fresh ephemeris position recomputation; geometry/time-alignment QA remains required.
- 20.46 MHz is not included or authorized.

## 9. Handoff impact

- Engineering handoff update required: no
- Paper handoff update required: no

This is planning only and introduces no new engineering or scientific fact. The two current handoffs remain the unique state sources.

## 10. No experiment executed

- raw: no (path/size metadata only)
- MATLAB: no
- SAGE: no
- batch: no
- data modified: no
