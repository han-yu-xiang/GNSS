# Frozen-baseline CIR, complex-alpha, and modeling-ledger audit — 2026-10-04

## Scope and provenance

This audit covers only `F1023_V70_D0117_P2 / G28 / ch1`, sample rate 10.23 MHz, after the Stage1–Stage4 historical regression returned `PASS_EXACT`. Raw-IQ access was authorized for this one scene. The file was checked by path and audited size before execution; no raw-IQ SHA-256 was recomputed (`raw_iq_sha256=NOT_RECOMPUTED`). No other scene's raw IQ was read.

The frozen SAGE source SHA-256 remained `bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c`. CIR processing used the pre-per-window-RMS IQ branch, samplewise NAV-sign wipe, per-snapshot complex-mean/DC removal, tracking-Doppler wipe with the recorded Doppler sign, and tracked-rate GPS C/A code. It did not apply per-snapshot RMS normalization. The CIR is a one-millisecond coherent code-domain correlation on the frozen default delay grid. Fractional delays use PCHIP interpolation of integer-delay circular FFT correlations.

## CIR and PDP artifacts

- HDF5: `../../scenes/F1023_V70_D0117_P2/sage_results/rerun_20261003_frozen_v3/G28_ch1/G28_ch1_code_domain_cir.h5` (253,946,914 bytes).
- Metadata: `../../scenes/F1023_V70_D0117_P2/sage_results/rerun_20261003_frozen_v3/G28_ch1/G28_ch1_code_domain_cir_metadata.json`.
- CIR shape: 35,920 one-ms snapshots × 451 delay bins; 898 Stage0 windows × 40 snapshots per window.
- Delay grid: −5 through +40 samples in 0.1-sample steps, sourced from `default_sage_configuration`.
- There are 22,920 unique snapshot start samples. The time axis is nondecreasing; overlapping Stage0 windows intentionally retain repeated timestamps with distinct window/snapshot keys.
- `/raw_iq_rms` is the square root of mean raw complex-IQ power before NAV wipe, DC removal, or normalization, in ADC counts. Values are positive. Receiver gain/AGC calibration evidence was not available, so `amplitude_reference_status=UNKNOWN_RECEIVER_GAIN_OR_AGC`.
- Each 40 ms Stage0-window PDP is the arithmetic mean of the powers of its 40 one-ms CIR snapshots, not a coherent complex sum.

Read-back validation reported finite CIR values, positive raw-IQ RMS, a nondecreasing time axis, the fixed delay grid, and one-to-one PDP/Stage0 alignment. The stored 898 × 451 PDP exactly recomputes from the corresponding groups of 40 snapshot powers (`MAX_PDP_DIFF=0`).

## CIR-primary delay comparison

The [per-window comparison CSV](CIR_PRIMARY_DELAY_COMPARISON.csv) contains 54 Stage2-selected windows. The signed quantity is `pdp_minus_sage_delay_samples`. Its range is −4.0 to +32.5 samples, median +0.1 samples, and maximum absolute difference 32.5 samples. For example, window 38 has a SAGE primary delay of 1.6 samples and a dominant PDP peak at 34.1 samples (+32.5 samples difference).

This is a descriptive comparison only. No acceptance threshold was defined or applied, and these differences are not being labeled pass/fail.

## Complex-alpha export

`SAGE_COMPLEX_PATH_COEFFICIENTS.csv` contains 77 rows, preserving the Stage2 selected-path `(window_id, path_id)` sequence. Alpha values were read from the selected-order `stage2Fits.models{selectedOrder}.paths(path_id).alpha` in the relocated Stage2 MAT data. Every row records `SAGE_ALPHA_IS_FROM_WINDOW_NORMALIZED_IQ=YES`. Frozen Stage CSV/MAT files and schemas were not edited.

## Modeling ledger

`MPC_MODELING_LEDGER.csv` has exactly 77 rows, one for each Stage2 selected-path row:

| Class / status | Rows | Primary modeling pool |
| --- | ---: | ---: |
| `DIRECT_PATH` | 54 | No |
| `TRANSIENT_MPC` | 16 | No |
| `PERSISTENT_MPC` | 7 | Yes |
| `HIGH_CONFIDENCE_MPC` | 0 | Yes when present |

Thus `LEDGER_STAGE2_SELECTED_PATH_ROWS=77`, `DIRECT_PATH_ROWS=54`, `MULTIPATH_ROWS=23`, `MPC_COUNT=23`, and `PRIMARY_MODELING_POOL_COUNT=7`. Direct paths remain in the ledger as reference paths and are excluded from MPC and primary-pool counts. The Stage3-based persistent class/pool is not gated by Stage4.

Stage4 label counts are `YES=0`, `NO=3`, `UNMAPPED=20` for multipath rows; the 54 direct rows use `NA` where the Stage3/Stage4 multipath-oriented tables do not directly map. No nearest-neighbor threshold or guessed identity was used. Both Stage4 joint summaries selected L=1 and contained zero joint multipath paths; the `UNMAPPED` ledger rows remain unresolved rather than being interpreted as negative confirmation.

## Related records

- [Single-task baseline report](MAINLINE_SAGE_BASELINE_RERUN_20261003.md)
- [Strict baseline comparison](MAINLINE_SAGE_BASELINE_RERUN_COMPARISON.csv)
- [Complex path coefficients](SAGE_COMPLEX_PATH_COEFFICIENTS.csv)
- [Complete modeling ledger](MPC_MODELING_LEDGER.csv)
