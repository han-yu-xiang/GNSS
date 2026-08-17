# VTC Evidence-Priority Production Queue

**Audit date:** 2026-08-14  
**Scope:** 10.23 MHz full-SAGE production planning only  
**Execution status:** planning artifact; no request generated and no task executed

This queue is a VTC evidence-planning document. It does not change the immutable production manifest, authorize MATLAB/SAGE execution, or predict whether any candidate will produce a confirmed multipath event.

## 1. Current evidence summary

The current evidence baseline was read from the engineering and paper handoffs, the VTC workspace, the 10 MHz production manifest/summary, scene metadata, candidate inventory, and existing QA artifacts.

| Evidence area | Current bounded fact | Planning implication |
|---|---|---|
| Measurement and method | Real dynamic GPS L1 C/A raw-IQ chain, NAV-aided Stage0–Stage4 pipeline, and normal-user Windows execution chain are validated | The paper can proceed with the measurement and hierarchical path-extraction story |
| Reference behavior | `F1023_V70_D0117_P2` seven-PRN validation contains control-like, rejected-candidate, and confirmed Stage4 cases | Figure 3 / hierarchy evidence is already available |
| Cross-task validation | Wave-A G16/G25/G12 is completed validation evidence, distinct from formal A3 G16 | Demonstrates execution-chain reproducibility, not population statistics |
| Formal production | A1 G11: 3 events/3 paths; A2 G18: valid zero-event output; controlled G12: 3 events/3 paths | Confirmed and zero-event cases are already represented |
| Formal A3 G16 | Scientific artifact is usable for pipeline validation, but its historical `Resume=true` contract deviation rejects it as Batch A acceptance evidence | Do not rerun or reuse the old namespace |
| Environment classes | 10.23 MHz metadata contains Urban, Mountain/Valley, Highway/Open, and Special Reflective | Special Reflective has the largest current formal-production evidence gap |
| Elevation | Reference geometry includes LOW/MID/HIGH observations under the defined 0–30/30–60/60–90 degree bins | Do not claim complete elevation-conditioned results until window-level TOW geometry QA and denominators are complete |
| Path-level evidence | Confirmed delay, relative Doppler, and relative power examples already exist in reference/A1/G12 artifacts | New production should add independent scene/environment support rather than duplicate the same case |

The VTC target is not 67/67 tasks. The target is the smallest auditable set that closes the paper's minimum evidence gaps before manuscript finalization.

## 2. Evidence gaps

1. **Special Reflective formal production:** bridge-over-water and railway/communication-tower scenes are present in metadata, but no current accepted formal production task from those classes appears in the accepted count. This is the highest-value environment gap.
2. **Independent scene coverage:** current accepted production is concentrated in `F1023_V70_D0117_P4` and `F1023_V70_D0120_P1`; a small number of new scenes is more useful than many additional PRNs from one already represented scene.
3. **Bounded elevation/environment comparison:** LOW/MID/HIGH definitions and GSV-derived summaries exist, but window-level TOW alignment is still `Missing/Partial` in the evidence matrix. New production does not by itself solve this geometry limitation.
4. **Figure support:** the hierarchy funnel and a confirmed path example are already supportable. A new Special Reflective scene, Highway/Open scene, and a distinct Mountain/Valley scene would provide candidate sources for a bounded environment/elevation figure after QA.
5. **Statistical denominator:** event/path database, complete negative-window denominator, and a fitted statistical channel model remain planned/not started. No queue item should be described as proving an environment effect.

## 3. Candidate audit and eligibility gate

The source production manifest is:

`dataset_generation_logs/production_planning_10mhz_20260812/production_task_manifest_10MHz_v1.json`

with SHA-256:

`77c20c0ed6c84fa0348db429948a8bd4900b2e8d86a6d8843b159b9a7a35cf00`

The manifest contains 48 Batch A rows. The current read-only filesystem check found four Batch A target namespaces already present: A1 G11, controlled G12, A2 G18, and historical formal A3 G16. Therefore 44 rows remain eligible for a *new* queue review. The first three are accepted production tasks; the A3 G16 directory is protected historical evidence and is not an acceptance candidate.

Every one of the 44 rows in the eligible set passed the planning gates recorded in the candidate inventory: `sample_rate_hz=10230000`, complete recorded tracking/telemetry/navigation/trajectory/geometry inputs, unique channel mapping, no blocked flag, and absent target output directory. Raw files were not opened or read; sizes below are metadata/inventory values only and raw hashes were not recomputed.

## 4. Candidate scoring logic

The score is a transparent planning score, not a scientific score and not a multipath predictor. It is applied only after the hard eligibility gate.

```text
priority_score =
    4 * environment_gap
  + 2 * elevation_contribution
  + 3 * scene_novelty
  + 2 * figure_value
  + cost_proxy
  - same_scene_repeat_penalty
```

The fixed components are:

| Component | Values and interpretation |
|---|---|
| `environment_gap` | Special Reflective=5; Highway/Open=4; Mountain/Valley=3; Urban=1. The values reflect current evidence coverage, not expected event richness. |
| `elevation_contribution` | LOW/HIGH=3; MID=2; `not_observed_in_summary`=1. This is a diversification contribution only. Missing summary rows are not filled by inference. |
| `scene_novelty` | Scene without an accepted formal production result=3; scene already represented by accepted A1/A2 production=1. A scene with only the rejected A3 artifact is kept out of first-wave selection and remains protected. |
| `figure_value` | Special Reflective=3; Highway/Open=3; Mountain/Valley=2; Urban=1. This means potential source value for a bounded figure, not a predicted scientific result. |
| `cost_proxy` | Metadata raw size ≤2.7 GB=3; >2.7 and ≤3.7 GB=2; >3.7 GB=1. This is only a size proxy; no exact runtime is assigned. |
| `same_scene_repeat_penalty` | 1 when the eligible set contains more than one task for the same scene; otherwise 0. First-wave selection additionally enforces one task per scene. |

Deterministic tie-breaking is: higher score, higher evidence-gap value, a not-yet-used scene, preferred elevation needed by the first-wave balance (HIGH before LOW before MID), smaller metadata raw size, then lexical `scene_id/PRN`. This rule cannot use Stage1–Stage4 results or anticipated confirmed events.

## 5. Scored eligible Batch A task set

All rows below are `planned_not_started` queue candidates. `not observed in summary` means that the scene-level satellite summary has no row for that PRN; it is not an inferred elevation or a reason to mark the task invalid.

| Scene | PRN/ch | Environment | Geometry summary | Speed (km/h) | Raw-size proxy (GB) | Score |
|---|---:|---|---|---:|---:|---:|
| F1023_V70_D0120_P9 | G05/ch10 | Special Reflective | LOW, mean 19.327° | 70 | 3.17 | 42 |
| F1023_V70_D0120_P9 | G18/ch1 | Special Reflective | HIGH, mean 75.000° | 70 | 3.17 | 42 |
| F1023_V70_D0120_P9 | G26/ch6 | Special Reflective | HIGH, mean 73.000° | 70 | 3.17 | 42 |
| F1023_V70_D0120_P9 | G27/ch5 | Special Reflective | LOW, mean 22.000° | 70 | 3.17 | 42 |
| F1023_V70_D0120_P9 | G29/ch4 | Special Reflective | LOW, mean 28.000° | 70 | 3.17 | 42 |
| F1023_V70_D0120_P9 | G31/ch7 | Special Reflective | LOW, mean 29.000° | 70 | 3.17 | 42 |
| F1023_V70_D0120_P9 | G16/ch9 | Special Reflective | MID, mean 50.510° | 70 | 3.17 | 40 |
| F1023_V70_D0120_P9 | G28/ch11 | Special Reflective | not observed in summary | 70 | 3.17 | 38 |
| F1023_V70_D0122_P2 | G24/ch3 | Special Reflective | HIGH, mean 73.574° | 70 | 4.75 | 41 |
| F1023_V70_D0122_P2 | G15/ch8 | Special Reflective | MID, mean 41.426° | 70 | 4.75 | 39 |
| F1023_V70_D0122_P2 | G19/ch11 | Special Reflective | MID, mean 39.000° | 70 | 4.75 | 39 |
| F1023_V70_D0122_P2 | G10/ch6 | Special Reflective | not observed in summary | 70 | 4.75 | 37 |
| F1023_V70_D0122_P2 | G12/ch2 | Special Reflective | not observed in summary | 70 | 4.75 | 37 |
| F1023_V70_D0122_P2 | G13/ch5 | Special Reflective | not observed in summary | 70 | 4.75 | 37 |
| F1023_V70_D0122_P2 | G23/ch10 | Special Reflective | LOW, mean 23.000° | 70 | 4.75 | 41 |
| F1023_V80_D0117_P8 | G25/ch10 | Highway/Open | HIGH, mean 79.000° | 80 | 2.43 | 39 |
| F1023_V80_D0117_P8 | G29/ch9 | Highway/Open | HIGH, mean 67.000° | 80 | 2.43 | 39 |
| F1023_V80_D0117_P8 | G31/ch1 | Highway/Open | LOW, mean 21.000° | 80 | 2.43 | 39 |
| F1023_V80_D0117_P8 | G32/ch11 | Highway/Open | LOW, mean 21.000° | 80 | 2.43 | 39 |
| F1023_V80_D0117_P8 | G12/ch4 | Highway/Open | MID, mean 38.000° | 80 | 2.43 | 37 |
| F1023_V80_D0117_P8 | G28/ch6 | Highway/Open | MID, mean 50.000° | 80 | 2.43 | 37 |
| F1023_v90_D0117_P7 | G25/ch0 | Mountain/Valley | HIGH, mean 80.000° | 90 | 2.32 | 33 |
| F1023_v90_D0117_P7 | G29/ch11 | Mountain/Valley | HIGH, mean 65.000° | 90 | 2.32 | 33 |
| F1023_v90_D0117_P7 | G32/ch5 | Mountain/Valley | LOW, mean 22.000° | 90 | 2.32 | 33 |
| F1023_v90_D0117_P7 | G11/ch6 | Mountain/Valley | MID, mean 35.000° | 90 | 2.32 | 31 |
| F1023_v90_D0117_P7 | G12/ch10 | Mountain/Valley | MID, mean 39.000° | 90 | 2.32 | 31 |
| F1023_v90_D0117_P7 | G28/ch4 | Mountain/Valley | MID, mean 49.000° | 90 | 2.32 | 31 |
| F1023_V70_D0117_P4 | G25/ch7 | Mountain/Valley | HIGH, mean 83.000° | 70 | 2.47 | 27 |
| F1023_V70_D0117_P4 | G32/ch3 | Mountain/Valley | LOW, mean 28.000° | 70 | 2.47 | 27 |
| F1023_V70_D0117_P4 | G28/ch6 | Mountain/Valley | MID, mean 42.000° | 70 | 2.47 | 25 |
| F1023_V70_D0117_P4 | G29/ch9 | Mountain/Valley | MID, mean 56.000° | 70 | 2.47 | 25 |
| F1023_V70_D0117_P4 | G31/ch1 | Mountain/Valley | not observed in summary | 70 | 2.47 | 23 |
| F1023_V70_D0120_P5 | G18/ch2 | Urban | HIGH, mean 73.000° | 70 | 2.37 | 23 |
| F1023_V70_D0120_P5 | G23/ch0 | Urban | LOW, mean 16.000° | 70 | 2.37 | 23 |
| F1023_V70_D0120_P5 | G26/ch7 | Urban | HIGH, mean 74.000° | 70 | 2.37 | 23 |
| F1023_V70_D0120_P5 | G27/ch10 | Urban | LOW, mean 19.000° | 70 | 2.37 | 23 |
| F1023_V70_D0120_P8 | G18/ch9 | Urban | HIGH, mean 74.000° | 70 | 2.32 | 23 |
| F1023_V70_D0120_P8 | G23/ch11 | Urban | LOW, mean 19.000° | 70 | 2.32 | 23 |
| F1023_V70_D0120_P8 | G26/ch3 | Urban | HIGH, mean 73.214° | 70 | 2.32 | 23 |
| F1023_V70_D0120_P8 | G16/ch4 | Urban | MID, mean 50.000° | 70 | 2.32 | 21 |
| F1023_V70_D0120_P1 | G26/ch3 | Urban | HIGH, mean 74.000° | 70 | 3.41 | 16 |
| F1023_V70_D0120_P1 | G27/ch8 | Urban | LOW, mean 17.000° | 70 | 3.41 | 16 |
| F1023_V70_D0120_P1 | G29/ch5 | Urban | MID, mean 33.680° | 70 | 3.41 | 14 |
| F1023_V70_D0120_P1 | G31/ch9 | Urban | MID, mean 34.000° | 70 | 3.41 | 14 |

The table is a planning snapshot, not a replacement for a future immutable request. Before any task is executed, the current inventory/metadata, input paths, output namespace, hashes, and normal-user wrapper preflight must be revalidated.

## 6. Tier 1 — Immediate VTC priority

Tier 1 contains five candidates. It is deliberately scene-diverse and includes no prediction of a positive result:

| Tier-1 candidate | Scene / PRN / channel | Environment and elevation | Metadata cost proxy | VTC evidence value |
|---|---|---|---:|---|
| T1-1 | `F1023_V70_D0120_P9/G05/ch10` | Special Reflective; LOW, 19.327° | 3.17 GB | First formal production evidence for bridge-over-water context and LOW geometry |
| T1-2 | `F1023_V70_D0120_P9/G18/ch1` | Special Reflective; HIGH, 75.000° | 3.17 GB | Same new reflective scene with a complementary HIGH geometry case |
| T1-3 | `F1023_V80_D0117_P8/G25/ch10` | Highway/Open; HIGH, 79.000° | 2.43 GB | New open-road scene and a clearly bounded high-elevation control candidate |
| T1-4 | `F1023_V80_D0117_P8/G31/ch1` | Highway/Open; LOW, 21.000° | 2.43 GB | Alternative open-road LOW candidate if T1-3 is not selected |
| T1-5 | `F1023_v90_D0117_P7/G11/ch6` | Mountain/Valley; MID, 35.000° | 2.32 GB | New mountain scene and a mid-elevation candidate with modest cost proxy |

The T1 list closes the largest environment gap first and keeps the first execution wave small. `G05`, `G25`, and `G11` are selected because they produce one task per scene and, together, cover Special Reflective, Highway/Open, Mountain/Valley and LOW/HIGH/MID planning contexts. This is a coverage design choice, not a prediction of confirmed events.

## 7. Tier 2 — Secondary VTC support

Tier 2 is used only if the first wave leaves a matrix gap after independent QA:

- `F1023_V70_D0122_P2/G24/ch3` (Special Reflective, HIGH, 4.75 GB): second reflective setting near railway/communication infrastructure; deferred because it is a larger raw-size class.
- `F1023_V70_D0122_P2/G23/ch10` (Special Reflective, LOW, 4.75 GB): complementary low-elevation railway setting; same cost caveat.
- `F1023_V70_D0120_P9/G18/ch1` or another P9 PRN not selected in the first wave: additional bridge scene context only after the first P9 task is QA-passed.
- `F1023_V80_D0117_P8/G12/ch4` (Highway/Open, MID, 2.43 GB): controlled cross-scene PRN comparison candidate; not selected solely because previous G12 tasks had confirmed paths.
- `F1023_v90_D0117_P7/G25/ch0` and `F1023_v90_D0117_P7/G32/ch5`: high/low Mountain/Valley alternatives if the new mountain scene is needed for elevation balance.
- Remaining F1023_V70_D0117_P4 PRNs: only for within-scene replication after the new-scene evidence gap is reassessed; the scene already has accepted G11/G12 production outputs.

Tier 2 does not authorize execution and must be re-scored after each independent QA result.

## 8. Tier 3 — Defer

Tier 3 is the remaining eligible candidate set, especially repeated Urban PRNs from scenes already represented by accepted production or validation evidence, additional same-scene PRNs after one representative has been run, and any task whose only justification would be “more samples.” Defer also includes the protected formal A3 G16 namespace: it is not a new candidate and must not be resumed, overwritten, or relabeled.

The five manifest rows excluded from production planning as multi-channel blocked remain excluded; no automatic channel selection is permitted. The six 20.46 MHz scenes remain outside this queue.

## 9. First execution wave

```text
FIRST_WAVE =
  A: F1023_V70_D0120_P9 / G05 / ch10 / 10.23 MHz
  B: F1023_V80_D0117_P8 / G25 / ch10 / 10.23 MHz
  C: F1023_v90_D0117_P7 / G11 / ch6  / 10.23 MHz
```

Why these three first:

1. They are from three different scenes and three different metadata contexts rather than repeated PRNs from one scene.
2. Their geometry summaries provide a planned LOW/HIGH/MID spread: 19.327°, 79.000°, and 35.000° respectively. These are scene-level GSV summaries, not window-level event elevations.
3. Their metadata raw-size proxies are 3.17 GB, 2.43 GB, and 2.32 GB. They are suitable for a controlled wave relative to the known long-record risk; no exact runtime is asserted.
4. They target the Special Reflective and Highway/Open gaps while retaining a distinct Mountain/Valley comparison case.
5. All three are single-channel, input-complete, 10.23 MHz, output-absent, nonblocked rows in the read-only planning snapshot.

Execution policy for the wave remains one immutable request at a time: request generation -> normal-user preflight -> human Windows execution -> independent QA -> summary/evidence-matrix update -> decision on the next task. No request is generated by this planning document.

## 10. VTC minimum evidence stop condition

After the first wave and QA, production may stop and the manuscript may move to finalization when the following bounded conditions are met:

1. Each of the four metadata environment classes has at least one real, independently QA-passed evidence case usable in the paper, or the paper explicitly narrows its environment claim and records the missing class as a limitation.
2. LOW, MID, and HIGH have either confirmed path evidence or an explicitly QA-complete analysis sample with known denominators. The current summary geometry alone is insufficient for a strong window-level elevation claim.
3. At least one clear confirmed multipath path case is available with traceable Stage4 evidence; this is already available from existing A1/G12/reference artifacts.
4. At least one Stage4 rejection/control case is available; this is already available from the reference hierarchy validation.
5. At least one valid zero-confirmed-event production case is available; A2 G18 and formal scientific G16 provide such bounded cases, with G16's contract caveat retained.
6. The available confirmed paths are sufficient for bounded descriptive observations of excess delay, relative power, and relative Doppler, without claiming a fitted statistical channel model.
7. Figure 2 (representative confirmed path) and Figure 3 (hierarchical filtering/rejection/confirmation) can be generated from immutable, QA-passed artifacts. Figure 4 remains conditional on geometry/environment QA.

The stop condition does **not** require 67/67 tasks, a completed statistical model, equal samples per environment, or 20.46 MHz production. It also does not convert a zero-event task into a physical claim of no multipath.

## 11. Re-evaluation rule

After each completed first-wave task:

1. perform the independent execution/artifact/scientific QA;
2. update the read-only production summary and this VTC evidence matrix;
3. reassess environment, elevation, scientific-case, and figure gaps;
4. either select the next Tier 1/Tier 2 task or declare the minimum evidence stop condition satisfied;
5. generate a new immutable request only after that decision.

Evidence priority is not a license to select a task because it is expected to contain multipath. Confirmed events, zero-event outputs, rejections, and inconclusive outcomes are all legitimate evidence categories when reported under the fixed Stage4 criterion.

## 12. Provenance and safety

Planning sources:

- `dataset_generation_logs/production_planning_10mhz_20260812/production_task_manifest_10MHz_v1.json`
- `dataset_generation_logs/production_planning_10mhz_20260812/production_inventory_10MHz.csv`
- `dataset_generation_logs/production_planning_10mhz_20260812/scene_metadata_10MHz.csv`
- `dataset_generation_logs/production_monitoring_10MHz/production_summary_10MHz.csv`
- `dataset_generation_logs/production_monitoring_10MHz/batch_A_candidate_list.csv`
- `docs/GNSS_SAGE_ENGINEERING_HANDOFF_CURRENT.md`
- `docs/GNSS_SAGE_PAPER_HANDOFF_CURRENT.md`
- `docs/vtc2027_spring/VTC_PLAN.md`
- `docs/vtc2027_spring/EVIDENCE_MATRIX.md`
- existing reference, Wave-A, Wave-2A, A1, A2, formal A3 G16 and controlled G12 QA artifacts

No completed raw IQ content value was used for the queue or T1-1 dry-run. During T1-1 preparation an inadvertent raw hash invocation was terminated before completion; no raw hash was generated or used, and this does not authorize raw processing. No MATLAB, SAGE, batch production, raw-coarse, sampled SAGE, 20.46 MHz task, manifest, scene data, or existing result artifact was modified. The current production manifest remains the only task source; this queue is not an execution authorization.

## 13. T1-1 request state (2026-08-14)

`F1023_V70_D0120_P9/G05/ch10/10.23 MHz` has completed request preparation and non-MATLAB executor dry-run:

- Queue state: `REQUEST_PREPARED / READY_FOR_HUMAN_EXECUTION`
- Request: `dataset_generation_logs/batch_sage_execution_requests/vtc_priority_t1_1_d0120p9_g05_20260814/execution_request.json`
- Request SHA-256: `feebda81d6f541c012d0cd898deb0142cacd3e9d28fc83deb634cf827dd9c194`
- Dry-run: `accepted_rows=1`, `rejected_rows=0`, `matlab_invoked=false`, `resume_allowed=false`
- Output: absent at preparation time; no Stage0-Stage4 result exists for T1-1

This task is not `RUNNING`, `COMPLETED`, or `AVAILABLE RESULT`. The human normal-user wrapper execution and independent QA remain pending. T1-2 and T1-3 are not authorized by this update and no requests for them were generated.

## 14. T1-1 execution and independent QA result (2026-08-14)

The preparation-only state above is superseded by the real execution and independent QA record:

- Queue state: `QA_PASS / AVAILABLE`
- Task: `F1023_V70_D0120_P9/G05/ch10/10.23 MHz`
- Execution: `batch_sage_execution_20260814T060453Z`
- QA report: `docs/10MHz_FULL_SAGE_PRODUCTION_T1_1_G05_QA_REPORT.md`
- Runtime: `4696.042 s`
- Stage0/Stage1/Stage2/Stage3/Stage4: `2630` windows; `2630/113`; `452`; `12`; `8/8`
- Confirmed output under the fixed Stage4 criterion: `2 events / 2 paths`
- Output namespace: `scenes/F1023_V70_D0120_P9/sage_results/nav_sage_v2/G05`

T1-1 is now available as Special Reflective evidence. This does not authorize automatic execution, and T1-2/T1-3 remain pending Commander decision and independent request preparation.

## 15. T1-2 request preparation (2026-08-14)

Following the Commander decision after T1-1, the next independent candidate is `F1023_V80_D0117_P8/G25/ch10/10.23 MHz` (`Highway/Open`, HIGH planning context, mean elevation approximately `79.0°`). This current decision supersedes the earlier planning-table placement of `F1023_V80_D0120_P9/G18/ch1` as T1-2: no second PRN from the P9 Special Reflective scene was prepared, and no Special Reflective-HIGH request was generated. No T1-3 request was generated.

- Queue state: `REQUEST_PREPARED / READY_FOR_HUMAN_EXECUTION`
- Request: `dataset_generation_logs/batch_sage_execution_requests/vtc_priority_t1_2_v80p8_g25_20260814/execution_request.json`
- Request SHA-256: `efd3bec67010856cdf1196202369f927224403015048277f4f57116e5029bb43`
- Preflight: `VTC_T1_2_READY = YES`; unique `G25 -> ch10`, 10.23 MHz, provenance gates passed, output absent, global lock absent
- Dry-run: `accepted_rows=1`, `rejected_rows=0`, `matlab_invoked=false`, `new_only=true`, `resume_allowed=false`
- Output namespace: `scenes/F1023_V80_D0117_P8/sage_results/nav_sage_v2/G25` (absent at preparation time)
- Dry-run preview explicitly uses `Resume=false`; no MATLAB or SAGE was run.

The preparation-only state above is superseded by the execution and QA result below. T1-3 remains `NOT_PREPARED`.

## 16. T1-2 execution and independent QA result (2026-08-14)

T1-2 `F1023_V80_D0117_P8/G25/ch10/10.23 MHz` completed under the normal Windows-user execution chain and passed independent QA.

- Queue state: `QA_PASS / AVAILABLE`
- Execution ID: `batch_sage_execution_20260814T075945Z`
- QA report: `docs/10MHz_FULL_SAGE_PRODUCTION_T1_2_G25_QA_REPORT.md`
- Runtime: `3800.307 s`
- Stage0/Stage1/Stage2/Stage3/Stage4: `1142` windows; `1142/112`; `448` evaluations with L1/L2/L3/L4=`38/13/12/49`; `8` reliable centers; `8/8` joint-valid rows
- Confirmed output: `2 events / 2 paths` under the fixed Stage4 criterion
- Output namespace: `scenes/F1023_V80_D0117_P8/sage_results/nav_sage_v2/G25`

Highway/Open evidence is now available for one independently QA-passed scene. The HIGH/approximately 79° value remains scene/PRN planning context, not event-level elevation evidence. T1-3 Mountain/Valley remains a required evidence-gap candidate, but no request was generated and no task was started automatically.

## 17. T1-3 request preparation (2026-08-14)

Commander-required T1-3 preparation is now complete for `F1023_v90_D0117_P7/G11/ch6/10.23 MHz` (Mountain/Valley; MID planning context; mean elevation `35.0°`). This is the sole new request in this step; no Special Reflective or Highway/Open follow-up request was generated.

- T1-1: `QA_PASS / AVAILABLE`
- T1-2: `QA_PASS / AVAILABLE`
- T1-3: `REQUEST_PREPARED / READY_FOR_HUMAN_EXECUTION`
- Request: `dataset_generation_logs/batch_sage_execution_requests/vtc_priority_t1_3_v90p7_g11_20260814/execution_request.json`
- Request SHA-256: `7a1361445855244ca6ed6f9f640debe1533981c7d4490bab52f45132fb170d47`
- Preflight: `VTC_T1_3_READY = YES`; unique `G11 -> ch6`, 10.23 MHz, provenance gates passed, output absent, global lock absent
- Dry-run: `accepted_rows=1`, `rejected_rows=0`, `matlab_invoked=false`; command preview explicitly uses `Resume=false`
- Output namespace: `scenes/F1023_v90_D0117_P7/sage_results/nav_sage_v2/G11` (absent at preparation time)

At the preparation point T1-3 was pending normal-user Windows execution and independent QA. That preparation was not a production result and did not predict confirmed events, zero events, LOS behavior, or Mountain/Valley statistics.

## 18. T1-3 execution and independent QA result (2026-08-15)

T1-3 `F1023_v90_D0117_P7/G11/ch6/10.23 MHz` completed through the normal Windows-user wrapper and passed independent read-only QA.

- Queue state: `QA_PASS / AVAILABLE`
- Execution ID: `batch_sage_execution_20260815T132956Z`
- Execution log: `dataset_generation_logs/batch_sage_execution/batch_sage_execution_20260815T132956Z/batch_execution_log.csv`
- QA report: `docs/10MHz_FULL_SAGE_PRODUCTION_T1_3_G11_QA_REPORT.md`
- Runtime: `4901.428 s` (about `81.69 min`)
- Stage0: `1292` valid NAV symbols and `1288` complete 40 ms windows
- Stage1: `1288` scanned and `112` selected
- Stage2: `448` evaluations; final L1/L2/L3/L4=`45/16/37/14`
- Stage3: `10` reliable centers
- Stage4: `8` joint rows, `8/8` `joint_valid=1`
- Confirmed output: `1 event / 1 path` under the fixed Stage4 criterion
- Output namespace: `scenes/F1023_v90_D0117_P7/sage_results/nav_sage_v2/G11`

Mountain/Valley evidence is now available as one independently QA-passed task-level case. The scene-level MID planning context is not an event-level elevation assignment. The VTC minimum evidence stop condition remains `NOT_SATISFIED` because the evidence matrix still records window-level TOW geometry join as `Missing/Partial`; no T1-4 request is created. The next route is `event/path aggregation -> geometry/time-alignment QA -> figures -> manuscript`, subject to a new Commander decision.
