# Batch A Representative Task Candidates

Audit timestamp (UTC): `2026-08-13T06:47:29.240743+00:00`

## Scope and safety

This is a read-only audit of the 48 tasks in the production manifest batch `A_pipeline_validation_batch`. It does not read raw IQ contents, create an execution request, run MATLAB/SAGE/batch, or modify the manifest, metadata, inventory, or production artifacts.

Sources: `E:\GNSS_Multipath_Project\dataset_generation_logs\production_planning_10mhz_20260812\production_task_manifest_10MHz_v1.json`, `E:\GNSS_Multipath_Project\dataset_generation_logs\production_planning_10mhz_20260812\production_inventory_10MHz.csv`, `E:\GNSS_Multipath_Project\dataset_generation_logs\production_planning_10mhz_20260812\scene_metadata_10MHz.csv`, `E:\GNSS_Multipath_Project\dataset_generation_logs\production_monitoring_10MHz\production_summary_10MHz.csv`.

Raw checks use filesystem existence, file type, and size only; raw content and raw hashes were not read or recomputed.

## Audit summary

- Batch A tasks audited: **48**
- Ready and not started: **46**
- Production completed with current summary QA PASS: **2**
- Blocked: **0**
- Output present but not matched to a current QA PASS summary: **0**
- Ready environment distribution: Highway/Open=6, Mountain/Valley=12, Special Reflective=15, Urban=13

The manifest/inventory snapshot still describes the two already-produced tasks as not started. This audit resolves current status from the filesystem plus `production_summary_10MHz.csv`: `F1023_V70_D0117_P4/G11/ch2` and `F1023_V70_D0120_P1/G18/ch2` are therefore shown as completed here. The source manifest is unchanged.

## Recommended Top 5

These are candidates for a future representative production sequence only. They are not execution approvals and do not predict confirmed multipath events.

|Rank|Scene|PRN|Channel|Environment|Speed|Reason|Status|
|---:|---|---|---:|---|---:|---|---|
|1|F1023_V70_D0120_P5|G16|ch1|Urban|70|Urban residential scene; new production scene, unique channel, complete inputs and absent output. Adds an urban context without predicting scientific outcome.|ready_not_started|
|2|F1023_V70_D0120_P8|G16|ch4|Urban|70|Distinct urban-road scene; unique channel, complete inputs and absent output. Provides a second urban morphology for process continuity.|ready_not_started|
|3|F1023_V80_D0117_P8|G12|ch4|Highway/Open|80|Highway/Open scene at 80 km/h; unique channel, complete inputs and absent output. Adds open-road coverage to the representative set.|ready_not_started|
|4|F1023_v90_D0117_P7|G11|ch6|Mountain/Valley|90|Mountain/Valley winding-road scene at 90 km/h; unique channel, complete inputs and absent output. Adds a distinct terrain/speed context.|ready_not_started|
|5|F1023_V70_D0117_P4|G12|ch4|Mountain/Valley|70|Mountain ascending scene; unique channel, complete inputs and absent output. Continues a scene where a different PRN already has QA PASS, without predicting this PRN's result.|ready_not_started|

### Why this set is representative

The set spans five scenes and three non-special environment groups represented in Batch A: Urban, Highway/Open, and Mountain/Valley. Four entries introduce a scene not yet represented by a current production QA PASS; the fifth is a controlled same-scene continuation after the G11 production PASS. All five are single-channel, input-complete, 10.23 MHz tasks with absent output namespaces at audit time. The ordering is an execution-planning recommendation only; runtime and multipath outcome are not inferred for unexecuted tasks.

## Input and output gate

For each task, the CSV records raw path metadata-only existence, GNSS-SDR tracking/telemetry, NAV, trajectory, geometry CSV existence, channel uniqueness, sample rate, expected output directory, and current production status. No task was started.

Blocked gate deficiencies found: none among Batch A.

`batch_A_candidate_list.csv` is the complete 48-row audit table. `recommended_rank` is populated only for the five proposed candidates.

## Runtime context

No candidate-specific runtime is assigned. Historical context is limited to the already completed production tasks: G11 approximately 85 minutes and G18 approximately 129 minutes. These figures are not forecasts for the candidate tasks.

## Prohibited interpretations

- Environment labels describe the annotated measurement context, not a prediction of confirmed multipath.
- `ready_not_started` means only that the audited preconditions were present and the output namespace was absent; it is not a scientific result.
- `possible_multipath_richness_note` is a planning annotation about environmental diversity/reflection opportunity, not an event-count prediction.

## Handoff impact

This audit creates candidate-planning artifacts only and does not change engineering or paper facts. Neither handoff is updated.

## No experiment executed

- raw IQ content read: **no**
- MATLAB: **no**
- SAGE: **no**
- batch executor: **no**
- execution request created: **no**
- production data/artifacts modified: **no**
