# GPU Stage2 qualification summary

Scope: the frozen 14-window qualification manifest only. This is experimental evidence, not production qualification.

QUALIFICATION_WINDOWS_PLANNED=14
QUALIFICATION_WINDOWS_EXECUTED=14
PREVIOUS_PASS_RESULTS_REUSED=8
QUALIFICATION_WINDOWS_NEWLY_EXECUTED=6
RESULTS_RUN_LEVEL_ATTESTED=8
RESULTS_WITH_PER_WINDOW_EMBEDDED_SHA=6
CPU_PRODUCTION_REFERENCE_FAIL=0
CPU_PRODUCTION_REFERENCE_PASS=14
GPU_STRUCTURAL_FAIL=0
IDENTITY_GATE_FAIL=0
WINDOWS_WITH_AUTHORIZED_RAW_IQ_READ=6
RETRY_TRIGGERED_WINDOWS=7
RETRY_NOT_TRIGGERED_WINDOWS=7
RETRY_UNKNOWN_WINDOWS=0
GPU_STAGE2_QUALIFICATION=STRUCTURAL_PASS

New per-window records are in `results/current/`; unchanged legacy records remain in `results/`; aggregate rows are in `GPU_STAGE2_QUALIFICATION_RESULTS.csv`.

The eight historical PASS JSON files remain byte-identical to their c7 commit blobs and still have no per-window Frozen SHA field. Their separate [run-level attestation](HISTORICAL_8_WINDOW_RUN_PROVENANCE_ATTESTATION.md) ties them to the committed pre-execution SHA guard and contemporaneous snapshot. The prior Q_G06/W6850 identity-fail JSON is preserved; the corrected timestamp is recorded in the manifest and correction note.

## Selected performance windows

Three newly executed windows were selected by model order: one L1, one L3, and one L4. Timings are supporting measurements only; they do not determine qualification status.

| Qualification ID | L | CPU Stage2 (s) | GPU first (s) | GPU warm (s) | Transfer in (s) | Transfer out (s) | Compute speedup | Warm end-to-end speedup |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Q_G06_W6850 | 1 | 40.5040247 | 5.0311686 | 4.2219119 | 0.0657682 | 0.0028270 | 9.593763598 | 7.445002356 |
| Q_G06_W17194 | 3 | 39.9017027 | 11.3112455 | 10.7035119 | 0.1388302 | 0.0070312 | 3.727907538 | 3.341076488 |
| Q_G11_W9161 | 4 | 36.1938953 | 9.2514870 | 8.7940382 | 0.1759148 | 0.0090321 | 4.115730962 | 3.595386510 |

```ini
PERFORMANCE_WINDOWS=3
CPU_MEDIAN_STAGE2_TIME=39.9017027
GPU_MEDIAN_WARM_STAGE2_TIME=8.7940382
MEDIAN_COMPUTE_SPEEDUP=4.115730961914631
MEDIAN_END_TO_END_SPEEDUP=3.595386510020452
```

## Maximum observed CPU/GPU numeric differences

These are raw observed maxima across the 14 windows; no new tolerance was applied. Structural status is reported separately.

```ini
MAX_DELAY_ABS_DIFF=0
MAX_DOPPLER_ABS_DIFF=0
MAX_RELATIVE_POWER_ABS_DIFF=1.4210854715202004e-13
MAX_ALPHA_ABS_DIFF=1.2539879139791263e-15
MAX_PATH_SCORE_ABS_DIFF=1.1937117960769683e-11
MAX_RSS_ABS_DIFF=2.3283064365386963e-10
MAX_RSS_REL_DIFF=5.6919358877821749e-16
MAX_BIC_ABS_DIFF=4.5446313379216008e-10
MAX_BIC_REL_DIFF=9.0419370848885707e-12
STRUCTURAL_EQUIVALENCE=PASS
NUMERIC_DIFFERENCES_RECORDED=YES
```

No raw IQ, MAT, HDF5, or large Stage output is part of the review bundle.

Production GPU remains disabled; frozen CPU source remains unchanged; the remaining 85-task CPU batch remains paused.
