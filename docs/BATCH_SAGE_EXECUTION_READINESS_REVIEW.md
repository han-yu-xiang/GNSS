# Batch SAGE Execution Readiness Review

## 1. Review scope and decision

This review assesses whether the current batch plan is suitable for a small controlled SAGE pilot. It is based on the latest dry-run artifacts:

- `dataset_generation_logs/batch_sage/batch_sage_dry_run_20260808T113454Z/batch_sage_plan.csv`
- `dataset_generation_logs/batch_sage/batch_sage_dry_run_20260808T113454Z/batch_sage_plan_report.md`
- `dataset_generation_logs/batch_sage/batch_sage_dry_run_20260808T113454Z/batch_sage_plan_issues.csv`
- `dataset/dataset_inventory.csv`

**Readiness decision: conditional GO for a five-task, two-wave, serial pilot; NO-GO for unrestricted batch execution.**

The current plan contains enough clean tasks to test the execution path. However, it does not yet provide measured workload for any new task, has no 20.46 MHz Stage0/Stage2 estimate, and does not yet include a batch executor, task locking, a frozen parameter snapshot, or post-run output validation. These gaps prevent full batch execution.

This review did not run MATLAB/SAGE and did not modify the plan, inventory, pipeline, metadata, scene inputs, or existing SAGE results. The only new artifact is this requested review document.

## 2. Current task statistics

| Category | Count | Interpretation |
|---|---:|---|
| Total scene-PRN tasks | 124 | 19 scenes |
| `ready` | 92 | Passed current hard gates; output target absent |
| `not_started` / preflight blocked | 25 | Must not enter the first pilot |
| `completed_or_existing` | 6 | Existing protected `nav_sage_v2` results for reference G11/G12/G25/G28/G29/G32 |
| `skipped` | 1 | Historical protected G06 v1 baseline |
| Multi-channel/manual selection | 5 | All are blocked |
| Ready at 10.23 MHz | 64 | New-task estimates use a low-confidence reference prior |
| Ready at 20.46 MHz | 28 | Window and Stage2 estimates are currently unavailable |

The report’s “117 tasks with warnings” is not equivalent to 117 defective tasks. It consists primarily of workload-estimation warnings:

- 76 tasks: `window_estimate_reference_prior` for new 10.23 MHz tasks;
- 41 tasks: `window_estimate_unavailable` for 20.46 MHz tasks.

These estimation warnings do not by themselves block execution. The 25 blocked tasks are determined by input/mapping hard gates.

## 3. Analysis of the 25 blocked tasks

### 3.1 Root-cause counts

Issue rows overlap, so their counts must not be added directly. The 25 unique blocked tasks reduce to five task-level combinations:

| Root-cause combination | Unique tasks | First-pilot disposition |
|---|---:|---|
| Satellite geometry PRN missing only | 17 | Exclude; regenerate/verify geometry first, otherwise skip |
| Multi-channel + tracking-start warning | 3 | Exclude; manual channel evidence required |
| Multi-channel + geometry missing | 1 | Exclude; resolve both blockers |
| Multi-channel only | 1 | Exclude; manual channel evidence required |
| Unique channel + tracking-start warning | 3 | Exclude; verify tracking/telemetry start mapping, otherwise skip |
| **Total** | **25** | **All excluded from first pilot** |

Raw issue counts are:

- `satellite_geometry_prn_missing`: 18 issue rows;
- `ambiguous_tracking_channel`: 5 issue rows;
- `inventory_warning_nav_mapping_without_tracking_start`: 6 issue rows;
- `tracking_path_missing`: 5 issue rows;
- `telemetry_path_missing`: 5 issue rows.

The five tracking/telemetry “missing” rows are secondary effects of multi-channel tasks having no selected channel. The plan intentionally leaves `tracking_path` and `telemetry_path` blank until channel resolution. They do **not** prove that every candidate channel file is physically missing.

### 3.2 Detailed task disposition

| # | Scene | PRN | Ch./candidates | Blocking evidence | Fixability and recommendation |
|---:|---|---|---|---|---|
| 1 | `F1023_V120_D0121_P2` | G03 | 2 | Geometry lacks G03 | Regenerate/verify geometry from source NMEA/RINEX; otherwise skip |
| 2 | `F1023_V120_D0121_P2` | G06 | 6, 9 | Multi-channel; ch6 tracking-start warning | Potentially fixable after evidence review; do not auto-select ch9 |
| 3 | `F1023_V120_D0121_P2` | G12 | 5, 11 | Multi-channel; ch5 tracking-start warning | Potentially fixable after evidence review; do not auto-select ch11 |
| 4 | `F1023_V120_D0121_P2` | G19 | 0, 1, 3 | Multi-channel and geometry lacks G19 | Resolve channel and geometry; skip until both pass |
| 5 | `F1023_V120_D0121_P2` | G29 | 3, 10 | Multi-channel | Inspect candidate telemetry/tracking content; skip until unique |
| 6 | `F1023_V70_D0117_P4` | G31 | 1 | Geometry lacks G31 | Regenerate/verify geometry; otherwise skip |
| 7 | `F1023_V70_D0120_P9` | G23 | 3, 10 | Multi-channel; ch10 tracking-start warning | Potentially fixable after evidence review; do not auto-select ch3 |
| 8 | `F1023_V70_D0120_P9` | G28 | 11 | Geometry lacks G28 | Regenerate/verify geometry; otherwise skip |
| 9 | `F1023_V70_D0122_P2` | G10 | 6 | Geometry lacks G10 | Regenerate/verify geometry; otherwise skip |
| 10 | `F1023_V70_D0122_P2` | G12 | 2 | Geometry lacks G12 | Regenerate/verify geometry; otherwise skip |
| 11 | `F1023_V70_D0122_P2` | G13 | 5 | Geometry lacks G13 | Regenerate/verify geometry; otherwise skip |
| 12 | `F1023_V80_D0117_P8` | G29 | 9 | Unique map, but no tracking start | Verify ch9 telemetry PRN/start and usable NAV span; otherwise skip |
| 13 | `F2046_V30_D0131_P2` | G05 | 1 | Geometry lacks G05 | Regenerate/verify geometry; otherwise skip |
| 14 | `F2046_V30_D0131_P2` | G29 | 0 | Unique map, but no tracking start | Verify ch0 telemetry PRN/start and usable NAV span; otherwise skip |
| 15 | `F2046_V30_D0131_P2` | G31 | 2 | Unique map, but no tracking start | Verify ch2 telemetry PRN/start and usable NAV span; otherwise skip |
| 16 | `F2046_V30_D0131_P4` | G11 | 0 | Geometry lacks G11 | Regenerate/verify geometry; otherwise skip |
| 17 | `F2046_V30_D0131_P4` | G21 | 2 | Geometry lacks G21 | Regenerate/verify geometry; otherwise skip |
| 18 | `F2046_V30_D0131_P4` | G25 | 7 | Geometry lacks G25 | Regenerate/verify geometry; otherwise skip |
| 19 | `F2046_V30_D0203_P2` | G22 | 7 | Geometry lacks G22 | Regenerate/verify geometry; otherwise skip |
| 20 | `F2046_V30_D0203_P2` | G23 | 3 | Geometry lacks G23 | Regenerate/verify geometry; otherwise skip |
| 21 | `F2046_V30_D0203_P2` | G25 | 10 | Geometry lacks G25 | Regenerate/verify geometry; otherwise skip |
| 22 | `F2046_V60_D0129_P1` | G15 | 4 | Geometry lacks G15 | Regenerate/verify geometry; otherwise skip |
| 23 | `F2046_V60_D0129_P3` | G19 | 2 | Geometry lacks G19 | Regenerate/verify geometry; otherwise skip |
| 24 | `F2046_V60_D0129_P3` | G28 | 3 | Geometry lacks G28 | Regenerate/verify geometry; otherwise skip |
| 25 | `F2046_V60_D0202_P1` | G28 | 10 | Geometry lacks G28 | Regenerate/verify geometry; otherwise skip |

### 3.3 Which blockers are fixable?

**Potentially fixable without changing SAGE:**

- The five multi-channel tasks can be resolved by a separate read-only channel-validation procedure that examines candidate tracking/telemetry content and produces an explicit resolution manifest.
- The three unique-channel tracking-start warnings may be cleared only if channel-specific telemetry/tracking evidence shows the expected PRN, a valid start, and enough continuous NAV symbols.
- Geometry-only tasks may become ready if the existing NMEA/RINEX sources actually contain the missing PRN and geometry can be regenerated under an explicitly authorized preprocessing step.

**Should remain skipped if evidence is unavailable:**

- Any multi-channel task that cannot be reduced to one uniquely supported channel;
- Any task whose telemetry has no valid tracking start or usable NAV-symbol span;
- Any geometry-missing task where the source trajectory/navigation data do not observe that PRN;
- All 25 blocked tasks in the first pilot, even if a likely channel can be guessed from warning text.

Relaxing the geometry hard gate would permit more SAGE runs but would break the current scene×PRN×elevation database objective. Such a policy change must be explicit and versioned; it must not be introduced inside the executor.

## 4. Multi-channel tasks and manual selection strategy

| Scene | PRN | Candidates | Existing clue | Recommended strategy |
|---|---|---|---|---|
| `F1023_V120_D0121_P2` | G06 | 6, 9 | ch6 has `nav_mapping_without_tracking_start` | Compare both channel telemetry PRN/start/TOW continuity and tracking coverage; ch9 is only a hypothesis until verified |
| `F1023_V120_D0121_P2` | G12 | 5, 11 | ch5 has the warning | Compare both candidates; ch11 is only a hypothesis until verified |
| `F1023_V120_D0121_P2` | G19 | 0, 1, 3 | No warning identifies a loser; geometry also missing | Require positive evidence for one channel and regenerate geometry; otherwise skip |
| `F1023_V120_D0121_P2` | G29 | 3, 10 | No warning distinguishes candidates | Require positive evidence for one channel; otherwise skip |
| `F1023_V70_D0120_P9` | G23 | 3, 10 | ch10 has the warning | Compare both candidates; ch3 is only a hypothesis until verified |

The channel-resolution procedure should record:

- scene, PRN, all candidate channels;
- candidate tracking/telemetry paths and sizes;
- telemetry PRN identity, valid start, TOW span and continuity;
- tracking time coverage and usable CN0/carrier-lock span;
- selected channel, rejected channels and evidence;
- reviewer, timestamp, resolution-rule version and source-file fingerprints.

It should produce a new immutable resolution manifest. It must not edit `dataset_inventory.csv` during the review itself and must never infer a channel solely because another candidate has a warning.

## 5. Recommended first pilot: five tasks in two waves

All five tasks are currently `ready`, have unique channels, pass input/geometry checks, have absent output targets, and are not part of the protected reference scene.

### Wave A — 10.23 MHz, serial

| Order | Scene | Scene PRN scale | PRN / ch. | Why selected | Current estimate |
|---:|---|---:|---|---|---|
| 1 | `F1023_V70_D0120_P7` | 4 PRNs | G16 / ch1 | Small scene matrix; PRN not used in reference validation; clean basic executor test | 319–1175 windows; typical 97 Stage2 candidates, low confidence |
| 2 | `F1023_v50_D0127_P1` | 5 PRNs | G25 / ch0 | G25 was the reference LOS/low-multipath control; useful cross-scene behavior check | 319–1175 windows; typical 97 Stage2 candidates, low confidence |
| 3 | `F1023_V70_D0122_P1` | 8 PRNs | G12 / ch6 | Larger scene matrix; G12 had confirmed multipath in the reference scene | 319–1175 windows; typical 97 Stage2 candidates, low confidence |

Wave A must run one task at a time. After each task, record actual Stage0 windows, Stage1 candidates, Stage2 evaluations, wall-clock time, peak memory, output size and external raw-I/O behavior. Stop the wave on any failed completion QA.

### Wave B — 20.46 MHz, serial and gated by Wave A

| Order | Scene | Scene PRN scale | PRN / ch. | Why selected | Current estimate |
|---:|---|---:|---|---|---|
| 4 | `F2046_V30_D0131_P4` | 8 PRNs | G18 / ch5 | Large scene matrix; unique channel and geometry coverage; different PRN from reference set | Window/Stage2 estimate unavailable |
| 5 | `F2046_V60_D0202_P1` | 5 PRNs | G32 / ch5 | Smaller 20.46 MHz scene; G32 confirmed multipath in reference at 10.23 MHz | Window/Stage2 estimate unavailable |

Wave B should begin only after Wave A confirms the executor, output validator and resource logging. Run G18 first; evaluate actual Stage0/Stage1/Stage2 scale and resource use before releasing G32. Do not run the two 20.46 MHz tasks concurrently.

This selection covers both supported sample rates, scene matrices of 4/5/8 available PRNs, five different PRNs, one reference LOS-like PRN, two reference confirmed-multipath PRNs, and two PRNs not validated in the reference scene. These are algorithmic diversity criteria, not environment labels; current metadata does not provide verified environment classes.

## 6. Risks in `run_nav_sage_pipeline.m` for batch execution

### High-priority risks

1. **Fixed output namespace.** The pipeline writes to `scenes/<scene>/sage_results/nav_sage_v2/<PRN>`. The executor must reject every pre-existing directory immediately before launch; it cannot choose a new namespace without an explicit pipeline/output design change.
2. **Checkpoint/resume ambiguity.** Current outputs include progress/checkpoint MAT files. An interrupted directory must never be treated as a new task. Resume requires matching scene, PRN, channel, sample rate, pipeline hash and parameter set; otherwise the task remains blocked.
3. **No batch lock/state ownership inside the pipeline.** Two workers could target the same directory unless the executor obtains an external atomic task lock and rechecks the output after locking.
4. **No calibrated 20.46 MHz workload.** All 41 tasks at 20.46 MHz have `window_estimate_unavailable`; 28 pass other gates, but memory, runtime and output volume are not yet characterized.
5. **Low-confidence 10.23 MHz estimates.** The 319–1175 window range and 4.4/8.2/29.8% Stage2 ratios are reference priors, not measurements for the target scenes.
6. **External raw-IQ I/O.** Standard scenes use external raw storage. Concurrent jobs may saturate the storage path and can produce misleading performance/failure behavior.

### Operational and provenance risks

- A MATLAB exit code of zero is insufficient; Stage0–Stage4 files and cross-table invariants still require validation.
- Header-only Stage3/Stage4 CSV files may be valid zero-event results and must not be misclassified as failure.
- The current dry-run uses `parameter_set_id=not_recorded_dry_run`; a real executor must freeze the exact parameter set and command before running.
- `run_context.json` does not independently provide every desired pipeline/parameter provenance field. The executor must record pipeline SHA-256, plan ID, parameter snapshot, MATLAB version and invocation outside the scene result.
- One MATLAB process should execute one task. A task-level exception must not corrupt the status of other tasks.
- Automatic retry is unsafe. A failed task may leave valid checkpoints and partial output; retry/resume needs an explicit new attempt record.
- The executor must not update metadata or inventory to signal progress; status belongs in the batch state ledger.

## 7. Questions that must be confirmed before implementing the executor

1. **Parameter freeze:** What exact Pipeline V3 parameter set and SHA-256 will the executor bind to? `not_recorded_dry_run` is not sufficient.
2. **Output policy:** Is execution strictly limited to absent `nav_sage_v2/<PRN>` targets? The recommended answer for the pilot is yes.
3. **Resume policy:** Are partial directories always blocked pending explicit approval, or may a validated matching checkpoint resume automatically? The recommended pilot policy is explicit approval only.
4. **Concurrency:** Will the pilot be forced to one MATLAB process at a time? The recommended answer is yes for both waves.
5. **Stop policy:** Does any nonzero exit or output-QA failure stop the remaining wave? The recommended answer is yes.
6. **Resource logging:** How will wall-clock, peak memory, raw-I/O rate, output size and MATLAB exit status be captured per task?
7. **MATLAB environment:** Which MATLAB version, license mode and required toolboxes are approved and recorded in the manifest?
8. **Disk-space gate:** What minimum free-space threshold must be satisfied before each task?
9. **Timeout:** What per-stage or per-task timeout is acceptable without killing a healthy long Stage2 run?
10. **Geometry policy:** Will geometry remain a hard gate? The recommended answer is yes for the first pilot and database-ready runs.
11. **Channel-resolution authority:** Who approves a manual channel selection and where is the immutable resolution manifest stored?
12. **Output completion QA:** Which exact CSV/MAT files and count invariants must pass before status becomes `completed`?
13. **Database handoff:** Should successful tasks be queued for ingestion only after completion QA, with ingestion failure kept separate from SAGE failure? The recommended answer is yes.
14. **Plan immutability:** Will the executor consume an explicit five-task allowlist derived from this plan rather than all 92 ready rows? The recommended answer is yes.

## 8. Required executor acceptance conditions

Before any MATLAB launch, the executor should demonstrate in a non-executing test that it can:

- load the immutable plan and an explicit pilot allowlist;
- refuse all 25 blocked tasks, six existing results and protected G06;
- refuse all five multi-channel tasks;
- obtain an atomic task lock and recheck target absence;
- verify every input path and file size immediately before execution;
- verify pipeline/parameter hashes;
- construct but not execute the exact MATLAB command in a command-preview mode;
- append status transitions without modifying the original plan;
- preserve partial outputs/checkpoints on failure;
- run completion QA and create a database-ingestion request only after success.

## Current Status

The project is ready to implement and dry-test a **serial, allowlist-based batch executor**, but it is not ready for unrestricted batch SAGE. The recommended first execution set is the five-task, two-wave pilot in Section 5. All 25 blocked tasks remain excluded, all reference results remain protected, and no task should run until the executor questions and acceptance conditions above are resolved.
