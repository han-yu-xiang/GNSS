# 10 MHz Full SAGE Production A3 G16 Independent QA Report

## Task information

- Scene: `F1023_V70_D0120_P5`
- PRN: `G16`
- Tracking channel: `ch1`
- Sampling rate: `10,230,000 Hz`
- Request ID: `windows_production_10mhz_a3_d0120p5_g16_20260813`
- Request: `dataset_generation_logs/batch_sage_execution_requests/production_10mhz_a3_d0120p5_g16_20260813/execution_request.json`
- Request SHA-256: `629e22444baa3ae7cede6584ec486312cceb7be541e443eab4c30d53dfa8a094`
- Execution ID: `batch_sage_execution_20260813T073512Z`
- Execution log: `dataset_generation_logs/batch_sage_execution/batch_sage_execution_20260813T073512Z/batch_execution_log.csv`
- Output: `scenes/F1023_V70_D0120_P5/sage_results/nav_sage_v2/G16/`

This report is read-only QA. No raw IQ content was read, and no MATLAB, SAGE, manifest, request, code, handoff, production summary, or existing result was modified.

## Execution

### Request and provenance validation

PASS for identity and hashes:

- Request SHA recomputed from the actual request file and matched the recorded SHA.
- Production manifest SHA in the request matched the current manifest: `77c20c0ed6c84fa0348db429948a8bd4900b2e8d86a6d8843b159b9a7a35cf00`.
- Production task record SHA matched the request.
- Pipeline, executor and Windows wrapper hashes matched the request.
- Approved scope matched `F1023_V70_D0120_P5/G16/ch1/10230000`.
- Inventory mapping was unique: `G16 -> ch1`.
- Metadata, tracking, telemetry, navigation, trajectory and both geometry hashes matched the request provenance.
- Raw IQ was checked only by path and size: file exists and is `2,541,355,520` bytes; raw content was not opened and raw SHA was intentionally not recomputed.

### Execution status

The execution receipts show:

- Windows identity: `TJ-CHANNEL\\Jing_`
- PowerShell: `7.6.4`
- MATLAB: `D:\\Program Files\\Matlab\\bin\\matlab.exe`
- MATLAB smoke marker: present (`MATLAB_STARTUP_OK`)
- MATLAB smoke exit code: `0`
- Python executor exit code: `0`
- Task exit code: `0`
- Task status: `completed`
- Runtime: `6497.683 s` (approximately `108.29 min`)
- No task error message or abnormal termination marker was recorded.

Execution evidence is in the request directory, the Windows runner receipt directory, the execution log, `status_history.jsonl`, the task log and `batch_execution_report.md`.

### Execution policy finding

The immutable request records `resume_allowed=false`, but the actual command recorded in the task log contains:

```text
'Resume', true
```

This is a real executor/request-policy mismatch. The available evidence indicates that this particular run was fresh rather than an actual reuse of prior output: the output namespace was absent at preflight, the task log says `Stage 0: building navigation-symbol catalog...`, and no stage was logged as loaded from an existing checkpoint. Nevertheless, the command did not strictly honor the frozen `resume_allowed=false` contract.

Therefore the execution evidence is operationally complete, but production policy conformance is **FAIL pending clarification or executor correction**. This report does not modify the executor or rerun the task.

## Artifact completeness

PASS for the G16 output artifact.

The output directory contains 21 non-empty files, including:

- `run_context.json` and `run_context.mat`
- Stage0 catalog, symbols, windows and MAT checkpoint
- Doppler-sign artifact
- Stage1 CSV, MAT and progress checkpoint
- Stage2 model-order, selected-window, selected-path CSV files, MAT and progress checkpoint
- Stage3 persistence, reliable-center CSV files and MAT checkpoint
- Stage4 joint-summary, joint-path CSV files and MAT checkpoint
- `G16_nav_sage_overview.png`

The output `run_context.json` matches scene `F1023_V70_D0120_P5`, PRN `G16`, channel `1`, sampling rate `10230000`, raw path and output namespace. No missing or zero-byte required output was found. The execution log and task log are retained outside the result directory under the execution namespace.

## Stage consistency

PASS.

| Stage | Result |
|---|---:|
| Stage0 valid NAV symbols | 1,211 |
| Stage0 complete 40 ms windows | 1,209 |
| Stage1 scanned windows | 1,209 |
| Stage1 selected candidate/fine windows | 118 |
| Stage2 model evaluations | 472 (118 windows × L=1--4) |
| Stage2 final selected L=1 | 49 |
| Stage2 final selected L=2 | 10 |
| Stage2 final selected L=3 | 22 |
| Stage2 final selected L=4 | 37 |
| Stage2 selected L≥2 | 69 |
| Stage2 selected L≥3 | 59 |
| Stage3 persistence rows | 165 |
| Stage3 reliable centers | 5 |
| Stage4 joint rows | 5 |
| Stage4 `joint_valid=1` rows | 5 |
| Stage4 `joint_multipath_count>0` rows | 0 |
| Confirmed multipath events | 0 |
| Confirmed multipath paths | 0 |

The count relationships are valid: 1,209 Stage0 windows were scanned by Stage1; 118 Stage1-selected windows were passed to Stage2; 5 reliable centers produced 5 Stage4 joint rows. Stage2 L≥2 selections and Stage3 reliable centers are not counted as confirmed multipath.

## Scientific validity

PASS for result validity and the current confirmation criterion.

Stage4 contains five non-empty joint summaries. All five have `joint_valid=1`, but all five select `joint_selected_L=1` and have `joint_multipath_count=0`. The Stage4 path table contains five direct-path rows, all with `is_multipath=0`. Consequently:

```text
confirmed event = joint_valid=1
                 AND joint_multipath_count>0
                 AND a path row with is_multipath=1
               = 0
```

This is a valid zero-confirmed-event production output under the current criterion. It must not be phrased as “G16 has no physical multipath.”

Gold-blind numerical sanity checks found:

- Stage0 C/N0, tracking Doppler, code frequency and carrier-lock values were finite for all 1,211 symbols.
- Stage1 main delay was `-1.0` to `1.8` samples and main Doppler was finite for all scanned windows.
- Stage2 selected-path excess delay was `0` to `4.4` samples (`0` to `0.44` chip), with Doppler offsets from approximately `-150.34` to `149.66 Hz` and relative power from approximately `-19.96` to `0 dB`.
- Stage4 critical numeric fields were finite for all five rows; joint relative Doppler and coherence were zero because only L=1 was selected.
- NaN values in Stage2 L=1 multipath-specific fields, such as minimum multipath power and minimum separation, are structurally not-applicable values rather than missing Stage4 output. Stage0 vehicle speed is NaN in rows using the recorded fallback speed-bound path and is not a path-parameter failure.
- No abnormal delay, Doppler, power, infinite value or malformed confirmed path was found.

## Overall decision

**REJECT for production acceptance at this time; conditional scientific artifact PASS.**

The G16 Stage0--Stage4 artifact is complete, internally consistent and scientifically valid as a zero-confirmed-event result. However, the recorded MATLAB command used `Resume=true` while the immutable request required `resume_allowed=false`. Although the logs show no actual checkpoint reuse in this run, an independent QA cannot mark the production execution contract fully compliant while this mismatch remains unresolved.

The G16 artifact may be retained as an immutable QA artifact and can be used for limited Pipeline Validation discussion as a completed run with the policy deviation explicitly disclosed. It should not yet authorize Batch A continuous production.

Before continuing Batch A, the project owner must resolve the executor/request semantics so that the actual MATLAB invocation honors `resume_allowed=false` for a `new_only` request, then perform the prescribed read-only acceptance check. No SAGE rerun is requested by this report.

## Handoff impact

- Engineering handoff update required: no; this QA report records the finding but the user requested no handoff update.
- Paper handoff update required: no; the zero-event result is not promoted to a paper-state update before production acceptance is resolved.

## Execution restrictions confirmed

- raw IQ content read: no
- MATLAB/SAGE rerun: no
- existing output modified: no
- manifest/request modified: no
- production summary modified: no
