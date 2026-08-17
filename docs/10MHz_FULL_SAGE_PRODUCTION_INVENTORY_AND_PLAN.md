# 10.23 MHz Full-SAGE Production Inventory and Planning Audit

Date: 2026-08-12. This is a read-only planning audit, not an execution authorization and not a SAGE result. The detailed machine-readable inventory is `dataset_generation_logs/production_planning_10mhz_20260812/production_inventory_10MHz.csv`.

## 1. Scope and evidence policy

- Source inventory: `dataset/dataset_inventory.csv`; SHA-256: `a626112b98b0b22274a6c5223defe8138c59544e8984979468f52a0b0fa4a16b`.
- Current engineering and paper handoffs were read and their source hashes were recorded in `dataset_generation_logs/production_planning_10mhz_20260812/audit_manifest.json`.
- Scene `metadata.json`, GNSS-SDR directories, navigation, trajectory, satellite geometry, and existing SAGE result files were inspected.
- Raw IQ was not opened or processed. Raw status means only metadata/inventory path existence and nonzero filesystem size; no raw content hash was recomputed.
- No MATLAB, SAGE pipeline, batch executor, raw-coarse code, or execution request was run or generated.
- Existing scene data, metadata, inventory, SAGE results, hashes, and both current handoffs were not modified.

## 2. Inventory totals

| Metric | Evidence-based value |
|---|---:|
| 10.23 MHz scenes | 13 |
| scene-PRN tasks | 83 |
| unique-channel tasks | 78 |
| multi-channel tasks requiring human selection | 5 |
| existing SAGE task namespaces | 11 |
| tasks with existing Stage0 window catalogs | 11 |
| observed Stage0 windows across existing catalogs | 28499 |
| observed confirmed event rows | 15 |
| observed confirmed path rows | 18 |

The status categories are mutually exclusive per task. `Completed` uses a strict Stage0-Stage4 chain check; the protected G06 legacy directory is treated as a complete historical baseline even though it lacks modern run-context files.

## 3. Task status classification

| Status | Count | Operational meaning |
|---|---:|---|
| Completed | 11 | Existing Stage0-Stage4 files are present and non-empty; eligible for read-only ingest after provenance/QA review. |
| Partial | 0 | Some result files exist but the chain is incomplete; no automatic resume is implied. |
| Not started | 67 | Inputs appear prepared and no required SAGE output file exists. |
| Invalid/Blocked | 5 | Evidence shows a hard gate, currently unresolved multi-channel mapping; not an algorithm result. |

### 3.1 Completed tasks

| Scene | PRN | Channel | Stage0 windows | Stage1 rows | Stage2 selected | Stage3 reliable centers | Stage4 summary rows | Confirmed events | Confirmed paths | Namespace |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| F1023_V120_D0121_P2 | G11 | 0 | 15210 | 15210 | 67 | 0 | 0 | 0 | 0 | nav_sage_v2/G11 |
| F1023_v50_D0127_P1 | G25 | 0 | 2339 | 2339 | 106 | 0 | 0 | 0 | 0 | nav_sage_v2/G25 |
| F1023_V70_D0117_P2 | G06 | 4 | 319 | 319 | 95 | 2 | 2 | 2 | 4 | G06_nav_sage_v1_legacy_protected |
| F1023_V70_D0117_P2 | G11 | 5 | 1175 | 1175 | 101 | 7 | 7 | 1 | 1 | nav_sage_v2/G11 |
| F1023_V70_D0117_P2 | G12 | 6 | 1175 | 1175 | 96 | 4 | 4 | 2 | 2 | nav_sage_v2/G12 |
| F1023_V70_D0117_P2 | G25 | 0 | 1175 | 1175 | 52 | 0 | 0 | 0 | 0 | nav_sage_v2/G25 |
| F1023_V70_D0117_P2 | G28 | 1 | 898 | 898 | 54 | 2 | 2 | 0 | 0 | nav_sage_v2/G28 |
| F1023_V70_D0117_P2 | G29 | 7 | 1175 | 1175 | 77 | 1 | 1 | 1 | 1 | nav_sage_v2/G29 |
| F1023_V70_D0117_P2 | G32 | 11 | 1175 | 1175 | 117 | 11 | 8 | 2 | 3 | nav_sage_v2/G32 |
| F1023_V70_D0120_P7 | G16 | 1 | 2229 | 2229 | 104 | 11 | 8 | 4 | 4 | nav_sage_v2/G16 |
| F1023_V70_D0122_P1 | G12 | 6 | 1629 | 1629 | 107 | 11 | 8 | 3 | 3 | nav_sage_v2/G12 |

The completed set is: reference scene seven PRNs (G06 legacy protected, G11, G12, G25, G28, G29, G32), Wave-A G16/G25/G12, and Wave-2A `F1023_V120_D0121_P2/G11/ch0`. The reference G06 namespace is `sage_results/G06_nav_sage_v1` and is immutable legacy baseline evidence.

### 3.2 Blocked tasks

| Scene | PRN | Channel candidates | Blocker |
|---|---|---|---|
| F1023_V120_D0121_P2 | G06 | 6;9 | multi_channel_manual_selection_required |
| F1023_V120_D0121_P2 | G12 | 5;11 | multi_channel_manual_selection_required |
| F1023_V120_D0121_P2 | G19 | 0;1;3 | multi_channel_manual_selection_required |
| F1023_V120_D0121_P2 | G29 | 3;10 | multi_channel_manual_selection_required |
| F1023_V70_D0120_P9 | G23 | 3;10 | multi_channel_manual_selection_required |

These five tasks have multiple inventory channel candidates: `F1023_V120_D0121_P2/G06` (ch6;ch9), `G12` (ch5;ch11), `G19` (ch0;ch1;ch3), `G29` (ch3;ch10), and `F1023_V70_D0120_P9/G23` (ch3;ch10). No automatic channel selection is authorized.

### 3.3 Not-started task coverage

- `F1023_V120_D0121_P2`: G03/ch2, G24/ch2, G25/ch5, G28/ch6, G32/ch7.
- `F1023_v50_D0127_P1`: G11/ch10, G28/ch4, G29/ch9, G31/ch5.
- `F1023_V70_D0117_P4`: G11/ch2, G12/ch4, G25/ch7, G28/ch6, G29/ch9, G31/ch1, G32/ch3.
- `F1023_V70_D0120_P1`: G18/ch2, G26/ch3, G27/ch8, G29/ch5, G31/ch9.
- `F1023_V70_D0120_P5`: G16/ch1, G18/ch2, G23/ch0, G26/ch7, G27/ch10.
- `F1023_V70_D0120_P7`: G18/ch4, G26/ch6, G31/ch8.
- `F1023_V70_D0120_P8`: G16/ch4, G18/ch9, G23/ch11, G26/ch3.
- `F1023_V70_D0120_P9`: G05/ch10, G16/ch9, G18/ch1, G26/ch6, G27/ch5, G28/ch11, G29/ch4, G31/ch7.
- `F1023_V70_D0122_P1`: G13/ch5, G14/ch9, G15/ch8, G17/ch2, G19/ch11, G22/ch4, G24/ch7.
- `F1023_V70_D0122_P2`: G10/ch6, G12/ch2, G13/ch5, G15/ch8, G19/ch11, G23/ch10, G24/ch3.
- `F1023_V80_D0117_P8`: G12/ch4, G25/ch10, G28/ch6, G29/ch9, G31/ch1, G32/ch11.
- `F1023_v90_D0117_P7`: G11/ch6, G12/ch10, G25/ch0, G28/ch4, G29/ch11, G32/ch5.

The complete row-level inventory, including raw path/size metadata, GNSS-SDR/NAV/trajectory/geometry status, stage status, result location, and provenance flags, is in the CSV. No values in that CSV are inferred from a scene name.

## 4. Paper-dataset suitability

| Suitability | Evidence-based interpretation |
|---|---|
| Recommended for paper dataset | Completed modern Stage0-Stage4 chain, unique channel, prepared inputs, and QA/provenance review available. |
| Potentially usable | Input-ready not-started unique-channel task, or protected G06 legacy baseline whose Stage chain exists but modern context is incomplete. Requires completion/ingest QA. |
| Needs completion | Partial output or a task without a completed Stage4 chain. |
| Excluded | Current evidence has an unresolved hard gate, including multi-channel ambiguity. It may become usable only after a new explicit channel decision and manifest. |

On this audit, 10 completed modern tasks are recommended after ordinary dataset-ingest QA; G06 is potentially usable as protected historical baseline; 67 unique-channel tasks are potentially usable but not started; 5 multi-channel tasks are excluded until channel selection is frozen. The detailed per-task suitability field is authoritative in the CSV.

## 5. Input and provenance findings

- All 13 ten-megasample-rate scene inventory rows report GNSS-SDR `SUCCESS`, RINEX NAV present, trajectory present, and satellite geometry `completed`; the audit also checked the expected scene-local files/directories.
- Raw IQ is external storage for these scenes. The audit verified path existence and nonzero filesystem size only. It did not open raw bytes, recompute raw SHA-256, or assert content integrity beyond the metadata-level check.
- Satellite geometry is the existing project product: primarily NMEA GSV elevation/azimuth with RINEX NAV used for PRN filtering, not a fresh broadcast-ephemeris position recomputation. Event-level time alignment remains a QA item.
- Inventory may contain nonblocking mapping warnings for PRNs not included in `available_prns`; these are retained in the CSV rather than silently corrected.
- A future task must freeze one channel when candidates are non-unique and must record the decision in a new immutable manifest. The batch executor must not guess.

## 6. Existing confirmed-event evidence

The existing completed outputs contain 15 confirmed Stage4 event rows and 18 associated multipath path rows across the 11 completed task records under this audit. The reference-scene and Wave-A breakdowns are documented in the current handoffs and QA reports; this inventory does not reinterpret Stage2 candidates or Stage3 reliable centers as confirmed events. A Stage4 zero-event file is a valid empty result only when the full chain and QA are complete.

## 7. Historical computation evidence and remaining-cost estimate

| Existing evidence | Observed scale | Planning implication |
|---|---|---|
| Reference G11 | 1,175 Stage0 windows; Stage1 about 27.5 min; Stage2 about 40.4 min | Short/medium full-scan baseline. |
| Wave-A G16 | 2,229 windows; full task about 3,913 s / 65.2 min | Medium-task baseline. |
| Wave-A G25 | 2,339 windows; full task about 2,725 s / 45.4 min | Medium-task lower observed bound. |
| Wave-A G12 | 1,629 windows; full task about 2,950 s / 49.2 min | Medium-task baseline. |
| Wave-2A G11 | 15,210 windows; Stage1 about 8.1 h; Stage2 about 11.4 h; total about 19.6 h | Long-scene budget warning. |

These are existing historical measurements, not new runs. The 67 not-started tasks have no Stage0 catalog in the result namespace, so their Stage1 window count is unknown and no per-task runtime is fabricated. A production estimate must be updated after Stage0 for each task. The remaining five blocked tasks require channel resolution before any Stage0/SAGE estimate is meaningful.

A safe planning rule is to reserve roughly 45鈥?5 minutes for a short task in the observed 1,600鈥?,400-window class, with a separate multi-hour reservation for long scenes; this is a planning band, not a guarantee or a measured prediction for unprocessed tasks. Stage1/Stage2 time is not assumed linear in raw size or window count.

## 8. Recommended production order (planned, not started)

1. Preserve the 11 completed records and perform read-only event/path ingest QA before treating them as the database baseline.
2. Expand scene coverage with one unique-channel task from each currently unrepresented scene, then independently QA before adding more PRNs from that scene:
   - `F1023_V70_D0117_P4/G11/ch2`
   - `F1023_V70_D0120_P1/G18/ch2`
   - `F1023_V70_D0120_P5/G16/ch1`
   - `F1023_V70_D0120_P8/G16/ch4`
   - `F1023_V70_D0120_P9/G05/ch10`
   - `F1023_V70_D0122_P2/G10/ch6`
   - `F1023_V80_D0117_P8/G12/ch4`
   - `F1023_v90_D0117_P7/G11/ch6`
3. After each first task passes QA, expand within that scene using new one-task immutable manifests. Prefer scene diversity before many same-scene PRNs.
4. Schedule the remaining unique PRNs in `F1023_V120_D0121_P2` with an explicit long-runtime window; resolve its four multi-channel tasks separately.
5. Do not schedule 20.46 MHz in this plan. Do not restart the paused raw-coarse/sampled-SAGE route.

These are recommendations only. No task was selected into an executable manifest by this audit and no task was launched.

## 9. Batch production design

### 9.1 Immutable manifest

Planned name: `production_task_manifest_10MHz.json`. Each entry should freeze `task_id`, `scene_id`, `PRN`, one manually resolved `tracking_channel`, `sample_rate_hz=10230000`, metadata/inventory hashes, raw path and a declared raw-hash policy, tracking/telemetry/NAV/trajectory/geometry provenance, pipeline script hash, expected Stage files, exact output namespace, `new_only=true`, `resume_allowed=false`, and `gold_labels_used_for_selection=false`. The manifest SHA-256 must be rechecked immediately before execution.

### 9.2 Output layout

The existing pipeline-authoritative output remains `scenes/<scene>/sage_results/nav_sage_v2/<PRN>/`. The protected reference legacy output remains `scenes/F1023_V70_D0117_P2/sage_results/G06_nav_sage_v1/`. A separate versioned production QA/index namespace should hold receipts, task summaries, event/path ingest manifests, and hashes; it must never replace or write into `sage_results`.

Recommended staged tables are `run`, `window`, `candidate`, `confirmed_event`, and `path`. The current confirmed criterion is `joint_valid=1` and `joint_multipath_count>0`. Labels should distinguish `confirmed_multipath`, `rejected_candidate`, and `los_reference`; incomplete or unscanned states must not enter the negative denominator as LOS.

### 9.3 Checkpoint and failure recovery

- Serial execution by default; one approved task at a time.
- Preflight every task: input existence, unique channel, 10.23 MHz, output collision, manifest/script hashes, disk space, and protected namespace checks.
- Preserve stdout/stderr, progress, checkpoint, partial files, and an interrupted/failed receipt on interruption or nonzero exit.
- Never delete, silently resume, or interpret partial Stage output as a paper result. Recovery requires a fresh reviewed namespace or an explicitly approved resume policy.
- Only after independent QA should an event/path ingest step mark a run usable for modeling.

## 10. Current blockers and limitations

- 67 unique-channel tasks are input-ready but not started; 5 tasks remain blocked by unresolved multi-channel mapping.
- Per-task Stage0 scale is unknown for unprocessed tasks; no raw-derived total runtime is claimed.
- Geometry is a prepared diagnostic product, not proof of exact event-time satellite position; geometry/time alignment QA remains required before LOW/MID/HIGH modeling.
- The 15,210-window G11 result demonstrates a many-hour full-scan throughput risk; runtime must be budgeted per task.
- Event/path database ingest and LOW/MID/HIGH statistical modeling remain Planned / Not started.
- 20.46 MHz is not adapted or authorized in this production plan.

## 11. Handoff impact

- Engineering handoff update required: no. This audit changes no code, execution state, result, hash, or safety rule.
- Paper handoff update required: no. It adds no new scientific experiment or result; it records a planning inventory in a separate report.

## 12. No experiment executed

- raw read: no (filesystem path and size metadata only)
- MATLAB: no
- SAGE: no
- batch: no
- data modified: no

## 13. Audit artifacts

- Report: `docs/10MHz_FULL_SAGE_PRODUCTION_INVENTORY_AND_PLAN.md`
- Full inventory CSV: `dataset_generation_logs/production_planning_10mhz_20260812/production_inventory_10MHz.csv`
- Audit manifest: `dataset_generation_logs/production_planning_10mhz_20260812/audit_manifest.json`
- Status summary: `dataset_generation_logs/production_planning_10mhz_20260812/status_summary.json`
