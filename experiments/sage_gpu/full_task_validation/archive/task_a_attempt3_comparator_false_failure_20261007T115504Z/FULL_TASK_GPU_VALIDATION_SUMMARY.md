# Full-Task GPU Candidate Validation

This is a lightweight run-level validation record, not a project handoff or a production result.

```ini
TASK_A=FAIL
TASK_B=NOT_RUN
FROZEN_SHA=bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c
CANDIDATE_SHA=5ea69f6b0ebc5e5be13cb109e4ec3eec30f377b52a5f22beed224164a035be3b
GPU_IDENTITY=NVIDIA GeForce RTX 4060 Laptop GPU
```

## TaskA

Task status: `FAIL`
Scene/PRN/channel: `F1023_V70_D0117_P2 / G28 / ch1`
Stage0–Stage4: `NOT_VERIFIED / NOT_VERIFIED / NOT_VERIFIED / NOT_VERIFIED / NOT_VERIFIED`
Stage2 evaluated/model/selected/path rows: ` /  /  / `; direct/MPC ` / `.
Stage3 persistence/reliable centers: ` / `; Stage4 joint results/paths/confirmation match: ` /  / `.

Numeric maxima (unthresholded):

- Delay / Doppler / relative power: `` /  / ``
- Alpha / path score: `` / ``
- RSS absolute/relative: `` / ``; BIC absolute/relative: `` / ``

Failure: `FullTaskGpuCandidate:COMPARISON_FAILED` — COMPARISON_FAILED STAGE2_MODEL_ORDERS_STRUCTURE_MISMATCH_RECORDING_TIME_S
Candidate namespace: `scenes/F1023_V70_D0117_P2/sage_results/gpu_candidate_fulltask_20261005/G28_ch1`; timestamp UTC: `2026-10-07T07:57:36.0558674+00:00`.

## TaskB

Status: `NOT_RUN`.

## Sequential decision diagnostics

minimum_checked_bic_surplus_cpu=NOT_AVAILABLE
minimum_checked_bic_surplus_gpu=NOT_AVAILABLE
minimum_checked_rss_surplus_cpu=NOT_AVAILABLE
minimum_checked_rss_surplus_gpu=NOT_AVAILABLE

## Runtime provenance note

One MATLAB startup smoke printed its marker but exited with code 3. No workaround was applied. Subsequent full startup, ArgumentList, function-resolution, and synthetic test validation passed. A Task A preflight must repeat startup smoke; any nonzero exit blocks before Task A execution or raw-IQ access.

