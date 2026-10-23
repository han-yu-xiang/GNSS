# Mainline 10.23 MHz CIR Task 4 Pilot Acceptance

**Check date:** 2026-10-23 UTC
**Disposition:** G28 baseline read-back PASS; G18/ch2 PASS; G23/ch0 PASS; remaining 80-task CIR batch NOT STARTED.

## Immutable release and execution identity

- Release directory: `E:\GNSS_Multipath_Project\dataset_generation_logs\channel_modeling\mainline_1023_cir_v1_20261023T060236191Z`
- Immutable `release_request.json` SHA-256: `b3824258548d12600dab19d6f6841cb280eeaac851f1d60b0b4cb17ba4a3bd31`
- Both pilots were request-bound, ordered G18/ch2 then G23/ch0. Each used a separate `runs/<run_id>/attempt_01/` output namespace, `attempt=1`, `resume=false`, the normal Windows user, Limited run level, one scheduled worker, and automatic retry disabled.
- Launch tasks: `GNSS-CIR-Mainline1023-20261023T060916763Z__G18_ch2` and `GNSS-CIR-Mainline1023-20261023T065240871Z__G23_ch0`.
- Source hashes bound at release and used for both pilots:

  | Source | SHA-256 |
  |---|---|
  | `scripts/channel_modeling/Invoke-Mainline1023CIRSingle.ps1` | `8d5e5a3c416254cdd8374a44d7fe24343f55a7ee115214ec7d31ebca6ed8aed6` |
  | `scripts/channel_modeling/export_gnss_code_domain_cir.m` | `e09e52bd22f77955997e2f0a08b1eca2ddd7479449ae83e20a58f9a3af9acadf` |
  | `scripts/channel_modeling/validate_gnss_code_domain_cir.m` | `b39980352ac205a4a56aeaaf193bbd54e0569d5e9a997bde5ff9fa061df43b02` |
  | Frozen SAGE entry | `bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c` |
  | Frozen SAGE configuration | `ac06ad3191ca7ca05480fb84c0465a5082c157f4eaad1ae3018e26e1abed1319` |

The post-pilot change to the PowerShell audit finalizer is recorded below; it did not participate in either MATLAB computation or alter either output. The immutable release request and receipts retain the exact executed source pins.

## Existing G28/ch1 baseline read-back

Request-bound read-back receipt: `dataset_generation_logs/channel_modeling/mainline_1023_cir_v1_20261023T060236191Z/baseline_readback/readback_receipt.json`.

- PASS, MATLAB exit 0; raw IQ was not read and the existing G28 outputs were not modified.
- 898 Stage0 windows × 40 one-ms snapshots; CIR shape 35,920 × 451 and PDP shape 898 × 451.
- PDP recomputation max difference: `0`.
- 54 primary-delay comparison rows; signed range `-4` to `32.5` samples, median `0.1`, maximum absolute difference `32.5` samples.
- Existing HDF5 size and UTC modification time matched the release snapshot.

## New pilot results

| Identity | Result / elapsed | Stage0 windows | CIR snapshots × delay bins | HDF5 size | PDP max recompute diff | Primary-delay comparison |
|---|---:|---:|---:|---:|---:|---|
| `run_20261003_F1023_V70_D0120_P1_G18_ch2` | PASS / 2,432.461 s (40m 32.46s) | 2,609 | 104,360 × 451 | 1,185,854,343 B (1.104 GiB) | 0 | n=115; signed median 0; median absolute 0.1; max absolute 0.4 samples |
| `run_20261003_F1023_V70_D0120_P5_G23_ch0` | PASS / 399.490 s (6m 39.49s) | 339 | 13,560 × 451 | 153,534,947 B (146.4 MiB) | 0 | n=89; signed median 0.1; median absolute 0.2; max absolute 39.6 samples |

Both HDF5 read-backs passed: exact Stage0 window ↔ PDP identity, window time/start alignment, snapshot-to-window mapping, snapshot index/sample/time alignment, monotonic nondecreasing time, all-finite CIR, positive raw-IQ RMS, and exact arithmetic-mean-of-40-powers PDP recomputation. The fixed 451-bin delay axis spans `-5` through `40` samples. Both MATLAB result records and pilot receipts identify the exact requested run, scene, PRN, and channel; MATLAB exit code is 0; `scientific_algorithm_modified=false`.

### Numerical comparison note

The delay CSV compares each Stage2 SAGE primary-path delay with the dominant peak of the per-window PDP; these are not required to be identical when a later multipath component dominates. G23 has one upper-tail row (`window_id=332`) where the SAGE primary delay is `0.4` samples and the PDP dominant peak is at the delay-grid maximum `40` samples, giving `+39.6` samples. Its median signed difference (`0.1`) matches the existing G28 baseline (`0.1`); its median absolute difference is `0.2` samples. G28 itself has a maximum absolute difference of `32.5` samples. The G23 edge peak is retained as a modeling/interpretation limitation, not hidden or converted into a new QA threshold. The frozen algorithm and delay grid were not changed.

Amplitude remains relative/un-calibrated: receiver gain/AGC metadata is unavailable and the result records `UNKNOWN_RECEIVER_GAIN_OR_AGC`; do not interpret CIR magnitude as calibrated absolute power. The G23 edge peak also means this pilot does not establish channel energy beyond the frozen `40`-sample grid.

## Output integrity and receipts

For each pilot, the runner wrote `pilot_receipt.json`, and the pilot audit records `status=PASS`. Independent checks confirmed every receipt output exists inside the release root and its byte length and SHA-256 match the receipt. No failure receipt exists for either new run.

G18 receipt: `dataset_generation_logs/channel_modeling/mainline_1023_cir_v1_20261023T060236191Z/runs/run_20261003_F1023_V70_D0120_P1_G18_ch2/pilot_receipt.json`.

| G18 output | Bytes | SHA-256 |
|---|---:|---|
| `G18_ch2_code_domain_cir.h5` | 1,185,854,343 | `6e5774baa9bcaa956e7ded4012d3d7d9f39245d921ce1bbf865d855eee4c7782` |
| `G18_ch2_code_domain_cir_metadata.json` | 8,127 | `0833ee2caa9522c8e1261262247a840c477d37e95650d4155d42ee4c8ce95ec9` |
| `G18_ch2_primary_delay_comparison.csv` | 5,177 | `0986b590cdbdbc06104b8532f6b11e0c157d1fe0915d5f536affddc001b5d0a6` |

G23 receipt: `dataset_generation_logs/channel_modeling/mainline_1023_cir_v1_20261023T060236191Z/runs/run_20261003_F1023_V70_D0120_P5_G23_ch0/pilot_receipt.json`.

| G23 output | Bytes | SHA-256 |
|---|---:|---|
| `G23_ch0_code_domain_cir.h5` | 153,534,947 | `a29e50acc1ba678942586501ed8a1527461f5c3d60ea8ded10740469d8989fbc` |
| `G23_ch0_code_domain_cir_metadata.json` | 8,109 | `1ebc9b5cc8e0ae35d5ec1fc27fb225c9ec4c95cd40301b6abd756c01bb2b96a2` |
| `G23_ch0_primary_delay_comparison.csv` | 3,859 | `41831927b0a3ac2e2caac5b516ffb62e6fcf8c0b15f5df6bfa127462e6884980` |

## Remaining-80 planning estimate; no production dispatch

The frozen cohort still has 80 new-required CIR identities after these two pilots, with 281,906 Stage0 windows. Using the slower measured output size per window, aggregate measured pilot throughput, and a 25% planning margin:

- Estimated remaining HDF5 upper budget: `160,166,469,154` bytes (149.17 GiB).
- Aggregate-throughput runtime estimate: `338,511` s (94.03 h); using the slower pilot rate: about 115.35 h.
- Required free space including the existing 100 GiB reserve: `267,540,651,554` bytes (about 249.1 GiB).
- E: free space at measurement: `438,462,578,688` bytes (408.35 GiB), so the estimate plus reserve fits at that sample. This is a forecast, not a guarantee or authorization to start the batch.
- No matching disk/USB I/O error was found since release creation; the pre-existing exFAT `Warning / Full Repair Needed` state remains accepted but unverified. No filesystem repair was run.

Current mainline summary remains `ALREADY_COMPLETE=1, COMPLETE=82, PENDING=4, IN_PROGRESS=0, FAILED=2`; all four quarantined mapping-warning tasks remain pending and both historical failed tasks remain failed. No remaining CIR task was dispatched.

## Audit-finalizer issue and scope

The execution-specific `pilot_audit.json` correctly records baseline read-back PASS and both per-run PASS receipts. The attempt to run `-FinalizePilotAudit` exposed a separate PowerShell StrictMode bug: `Get-PilotAudit` returns a `PSCustomObject` without optional `status` and `final_acceptance` properties, but the finalizer directly assigned to those absent properties. The command failed before replacing `pilot_audit.json` or creating `forecast_80_remaining.json`; the release request, receipts, and outputs are unchanged.

The branch now contains a minimal `Add-Member` helper and a regression test for initializing those optional properties while preserving existing audit members. The test was confirmed red before the fix and passes afterward (`Invoke-Mainline1023CIRSingle.Tests.ps1`: 36/36). Because the release is immutable and pins the pre-fix runner SHA, that patched runner was **not** used to re-finalize or mutate this release. This document is the final acceptance/forecast addendum for independent review; it does not replace or rewrite the per-run receipts.

## Decision

Task 4 pilot evidence is accepted for Gate D review with the numerical edge-peak caveat above. Keep the remaining 80 tasks stopped until independent review of this report and the Draft PR, then obtain an explicit separate production authorization. Do not merge main or modify the SAGE summary/outputs as part of Task 4.
