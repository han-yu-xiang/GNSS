# GPU Stage2 qualification summary

Scope: the frozen 14-window qualification manifest only. This is experimental evidence, not production qualification.

QUALIFICATION_WINDOWS_PLANNED=14
QUALIFICATION_WINDOWS_EXECUTED=8
SCENES_COVERED=2
L1_WINDOWS=2
L2_WINDOWS=3
L3_WINDOWS=2
L4_WINDOWS=1
CPU_PRODUCTION_REFERENCE_PASS=8
CPU_PRODUCTION_REFERENCE_FAIL=0
GPU_STRUCTURAL_PASS=8
GPU_STRUCTURAL_FAIL=0
IDENTITY_GATE_FAIL=1
RETRY_TRIGGERED_WINDOWS=4
RETRY_NOT_TRIGGERED_WINDOWS=4
RETRY_UNKNOWN_WINDOWS=1
AUTHORIZED_RAW_IQ_RANGES_READ=8
RAW_IQ_SAMPLES_PER_RANGE=409200
GPU_STAGE2_QUALIFICATION=INCOMPLETE_STOPPED_ON_IDENTITY_MISMATCH

The qualification stopped before reading `Q_G06_W6850` raw IQ. Its frozen manifest time is `163.771145454545 s`, while its formal Stage0/Stage1/Stage2 output consistently records `163.771145552297 s` (difference `9.7752007377494e-8 s`). The qualification manifest and selected window were not changed; no timestamp was inferred or repaired.

Per-window machine-readable records are in `results/`; aggregate rows are in `GPU_STAGE2_QUALIFICATION_RESULTS.csv`.

## Observed retry trace

`Q_G03_W173`, L3 residual-path initialization: candidate rank 1 (delay `2`, Doppler `-5401.146244779715 Hz`, score `38.95742749690587`) had minimum separation `0.7000000000000002` samples and was rejected with `REJECT_SEPARATION`. Candidate rank 2 (delay `4`, same Doppler, score `27.525929959768636`) had minimum separation `1.2999999999999998` samples and was accepted. This is the measured qualification trace, not a window-specific rule.

The completed windows all passed CPU-to-formal structural reference and GPU structural comparison. Numeric deltas are retained in the CSV; the largest GPU-vs-CPU values observed were: delay `0`, Doppler `0`, relative power `1.1013412404281553e-13`, complex alpha `7.9300963114645856e-16`, path score `1.1937117960769683e-11`, RSS `2.3283064365386963e-10`, RSS relative `5.6919358877821749e-16`, BIC `4.5446313379216008e-10`, BIC relative `8.9163844956875942e-12`.

No representative performance median is reported because the full 14-window set did not complete.

No raw IQ, MAT, HDF5, or large Stage output is part of the review bundle.

Production GPU remains disabled; frozen CPU source remains unchanged; the remaining 85-task CPU batch remains paused.
