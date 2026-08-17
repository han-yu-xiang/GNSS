# Batch A Representative Execution Preflight Report

## Task information

- Scene: `F1023_V70_D0120_P5`
- PRN: `G16`
- Tracking channel: `ch1`
- Sample rate: `10.23 MHz` (`10230000 Hz`)
- Batch: `A_pipeline_validation_batch`
- Purpose: `Batch A representative validation`
- Request ID: `windows_production_10mhz_a3_d0120p5_g16_20260813`
- Execution status: **NOT STARTED**

The task was selected as an ordinary single-channel Urban Batch A task with complete preparatory inputs, a unique G16-to-ch1 mapping, and an absent target output namespace. The selection is a production-process validation choice only; it does not predict multipath events or scientific results.

## Immutable request artifacts

- Request: `E:\GNSS_Multipath_Project\dataset_generation_logs\batch_sage_execution_requests\production_10mhz_a3_d0120p5_g16_20260813\execution_request.json`
- Request SHA-256: `629e22444baa3ae7cede6584ec486312cceb7be541e443eab4c30d53dfa8a094`
- Approved plan snapshot: `E:\GNSS_Multipath_Project\dataset_generation_logs\batch_sage_execution_requests\production_10mhz_a3_d0120p5_g16_20260813\approved_plan_snapshot.csv`
- Approved plan snapshot SHA-256: `cb77d8c6f9f88a19ce99d2557ea3242c2080a11097cf42bff26fd9c8e641e78b`
- Selected-task snapshot: `E:\GNSS_Multipath_Project\dataset_generation_logs\batch_sage_execution_requests\production_10mhz_a3_d0120p5_g16_20260813\selected_tasks_snapshot.csv`
- Selected-task snapshot SHA-256: `d2200c5d9be5b0de6a12390eef6c4ebb5c3d1e1a11845ef0981eb1533f93a8f6`

The historical batch plan did not contain this newly selected production task. Therefore, the request contains a new single-task plan snapshot derived from the unchanged production manifest. This does not modify the historical batch plan, production manifest, inventory, or any result artifact. The snapshot is the only plan presented to the existing wrapper for a future human-reviewed execution.

## Selection and source provenance

- Production manifest: `E:\GNSS_Multipath_Project\dataset_generation_logs\production_planning_10mhz_20260812\production_task_manifest_10MHz_v1.json`
- Production manifest SHA-256: `77c20c0ed6c84fa0348db429948a8bd4900b2e8d86a6d8843b159b9a7a35cf00`
- Production task ID: `F1023_V70_D0120_P5__G16`
- Production task record SHA-256: `c92131652edb3029747e2f37b1d507d0134401ae4e5978a051ce84ab8004ca1a`
- Production inventory SHA-256: `af368feba90797584d7690d4927ed32de604651a5a62662f4adce348a89e4bb4`
- Dataset inventory SHA-256: `a626112b98b0b22274a6c5223defe8138c59544e8984979468f52a0b0fa4a16b`
- Scene metadata: `E:\GNSS_Multipath_Project\scenes\F1023_V70_D0120_P5\metadata.json`
- Scene metadata SHA-256: `f4e7ea8f4a9fc0d6051de22d0150ceb64668d64061aff7ebc9f6f06585845ffa`

## Input validation

| Gate | Evidence | Result |
|---|---|---|
| Scene metadata | `scene_id=F1023_V70_D0120_P5`; standard scene; GNSS-SDR/navigation/trajectory/geometry completed; SAGE not run | PASS |
| Sample rate | Metadata and production manifest both report `10230000 Hz` | PASS |
| Inventory mapping | Production inventory reports `G16` candidate `1`, `channel_status=unique`; dataset inventory PRN map reports `G16:[1]` | PASS |
| Raw IQ path | `E:\AAGNSSSDR_input\raw_data\F1023_V70_D0120_P5.bin`, exists, nonzero size `2541355520` bytes | PASS; content not opened |
| Tracking | `...F1023_V70_D0120_P5_track_ch_1.mat`, exists, nonzero, SHA-256 `b54700d2c08dc4123826f4809e4c0e947fd5ef7437b879fd0fdf0f163329cb40` | PASS |
| Telemetry | `...F1023_V70_D0120_P5_telemetry_ch_1.dat`, exists, nonzero, SHA-256 `6e5b06be3d6aa9c3c05955667ac4dd6d5b358f402fa1a5b6854f004905be4843` | PASS |
| Navigation | `...navigation\rinex_nav\RINEXFILE.26N`, exists, nonzero, SHA-256 `273cdc5c89a16ccf01a020e26346e93bfb592c97b7647408d63e09e04689c670` | PASS |
| Trajectory | `...trajectory\F1023_V70_D0120_P5_trajectory.nmea`, exists, nonzero, SHA-256 `3353072cb953bde0003498b7a0a36e9cb8cc8983979ac91a5783176e20735706` | PASS |
| Satellite geometry | Elevation timeseries and summary CSVs both exist and match recorded hashes `856b22...ff650c` and `6eb6fa...f0a10` | PASS |
| Stage0 | Production manifest state is `not_started`; pipeline must generate/verify Stage0 at execution time | EXECUTION-TIME GATE |

The raw file was checked only by filesystem metadata. Its content and SHA-256 were not read or recomputed in this preparation task.

## Hash validation

| Component | SHA-256 |
|---|---|
| Production manifest | `77c20c0ed6c84fa0348db429948a8bd4900b2e8d86a6d8843b159b9a7a35cf00` |
| Pipeline `run_nav_sage_pipeline.m` | `5ff00366f2d71eff7945418ce484b0fedb7199f1144c2db2fb18268fe5b4b0ab` |
| Python executor `run_batch_sage.py` | `3d4856bdc74d169346ab10f99bf2e7cf94f825e2c835ab8ad76d9ed1d48bddb9` |
| Windows wrapper `Invoke-BatchSageWindows.ps1` | `bed851a978ac9f03d69ddbb2dee1e7b0d458424fed6fafffc3d7473e7676b616` |
| Approved plan snapshot | `cb77d8c6f9f88a19ce99d2557ea3242c2080a11097cf42bff26fd9c8e641e78b` |
| Selected-task snapshot | `d2200c5d9be5b0de6a12390eef6c4ebb5c3d1e1a11845ef0981eb1533f93a8f6` |
| Immutable request | `629e22444baa3ae7cede6584ec486312cceb7be541e443eab4c30d53dfa8a094` |

The request freezes `new_only=true`, `resume_allowed=false`, `max_parallel_matlab=1`, one ordered task, one allowed sample rate (`10230000 Hz`), `nav_sage_v2`, and `gold_labels_used_for_selection=false`.

## Output and protection gates

- Expected output: `E:\GNSS_Multipath_Project\scenes\F1023_V70_D0120_P5\sage_results\nav_sage_v2\G16`
- Output state at preflight: **does not exist**
- Global Windows runner lock: `E:\GNSS_Multipath_Project\dataset_generation_logs\batch_sage_execution\.windows_runner_active.lock` — **absent**
- Task lock for G16: **absent**
- Normal-user execution requirement: `TJ-Channel\Jing_`, non-administrator PowerShell 7
- Codex sandbox MATLAB execution: **not allowed**
- Existing G11, G18, reference-scene outputs, and `G06_nav_sage_v1`: detected as existing protected artifacts and are not target paths; none were modified.

## Execution readiness

**PREFLIGHT_RESULT: PASS — REQUEST_READY_FOR_HUMAN_EXECUTION**

This is a request/preflight PASS, not an execution or scientific QA result. Before any future execution, the normal-user wrapper must recompute the request hash and all frozen source hashes, recheck the output namespace and global lock, run its MATLAB startup smoke with marker plus exit code `0`, and retain its existing single-task/new-only/reference-protection gates. If any of those checks fails, execution must stop without MATLAB/SAGE launch or overwrite/resume.

## Handoff impact

No experiment or engineering state transition occurred, so neither handoff is updated.

- Engineering handoff update required: **no**
- Paper handoff update required: **no**

## No experiment executed

- raw IQ content read: **no**
- MATLAB: **no**
- SAGE: **no**
- batch executor: **no**
- production artifact modified: **no**
- existing SAGE result modified: **no**
