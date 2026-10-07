# Full-Task GPU Candidate Validation

This is a lightweight run-level validation record, not a project handoff or a production result.

```ini
TASK_A=PASS
TASK_B=PASS
FROZEN_SHA=bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c
CANDIDATE_SHA=5ea69f6b0ebc5e5be13cb109e4ec3eec30f377b52a5f22beed224164a035be3b
GPU_IDENTITY=NVIDIA GeForce RTX 4060 Laptop GPU
```

## TaskA

Task status: `PASS`
Scene/PRN/channel: `F1023_V70_D0117_P2 / G28 / ch1`
Stage0–Stage4: `PASS / PASS / PASS / PASS / PASS`
Stage2 evaluated/model/selected/path rows: `54 / 216 / 54 / 77`; direct/MPC `54 / 23`.
Stage3 persistence/reliable centers: `23 / 2`; Stage4 joint results/paths/confirmation match: `2 / 2 / true`.

Numeric maxima (unthresholded):

- Delay / Doppler / relative power: ``0 / 0 / 6.2350125062948791e-13``
- Alpha / path score: ``1.6592083686974716e-15 / 1.7962520360015333e-11``
- RSS absolute/relative: ``2.3283064365386963e-10 / 5.6908908730775017e-16``; BIC absolute/relative: ``4.5440629037329927e-10 / 3.6819019561807299e-11``

## TaskB

Task status: `PASS`
Scene/PRN/channel: `F1023_V120_D0121_P2 / G03 / ch2`
Stage0–Stage4: `PASS / PASS / PASS / PASS / PASS`
Stage2 evaluated/model/selected/path rows: `96 / 384 / 96 / 142`; direct/MPC `96 / 46`.
Stage3 persistence/reliable centers: `46 / 8`; Stage4 joint results/paths/confirmation match: `8 / 8 / true`.

Numeric maxima (unthresholded):

- Delay / Doppler / relative power: ``0 / 0 / 6.6080474425689317e-13``
- Alpha / path score: ``2.1798662911312568e-15 / 7.0485839387401938e-12``
- RSS absolute/relative: ``2.3283064365386963e-10 / 5.6952125339143077e-16``; BIC absolute/relative: ``5.4535576055059209e-10 / 7.3840627515281781e-12``

## Sequential decision diagnostics

minimum_checked_bic_surplus_cpu=-61.05695027582273 task=TaskA window=46 transition=L1_to_L2 accepted=false
minimum_checked_bic_surplus_gpu=-61.05695027509583 task=TaskA window=46 transition=L1_to_L2 accepted=false
minimum_checked_rss_surplus_cpu=-0.001584131400087608 task=TaskA window=46 transition=L1_to_L2 accepted=false
minimum_checked_rss_surplus_gpu=-0.0015841314000022578 task=TaskA window=46 transition=L1_to_L2 accepted=false

## Runtime provenance note

One MATLAB startup smoke printed its marker but exited with code 3. No workaround was applied. Subsequent full startup, ArgumentList, function-resolution, and synthetic test validation passed. A Task A preflight must repeat startup smoke; any nonzero exit blocks before Task A execution or raw-IQ access.

