# Mainline Stage2 measured-elevation and route audit

Audit date: 2026-10-24 (local project workspace)

## Scope and safeguards

This Task 7 audit used the frozen 83-task cohort and existing Stage2 ledger.
It did not run SAGE, MATLAB or CIR production, and did not read CIR/HDF5, MAT,
raw-IQ, or RINEX contents. All 205 file hashes recorded by the prior GSV
geometry audit were re-verified. RINEX files were checked by hash/size only.
Precise route coordinates and source-record paths are confined to the ignored
local output namespace; this report contains aggregate values only.

## Measured GSV elevation overlay

| Quantity | Audited value |
|---|---:|
| Frozen cohort tasks / scenes | 83 / 13 |
| Stage0-valid windows | 285,752 |
| Stage2 paths / selected windows | 16,761 / 7,847 |
| Same-scene, same-PRN measured GSV matches | 5,295 |
| Explicitly missing GSV matches | 2,552 |

Elevation is sourced only from checksum-valid, timestamped GPS GSV records.
The nine frozen missing-elevation task classifications remain `MISSING`; 728
selected windows in those tasks have no matching target-PRN GSV observation.
No values were imputed or derived from orbit calculations.

## Route overlay and coverage

The route runner verified the GSV audit's 205 input pins and exact cohort and
ledger identities. The 7,847 Stage2 `(run_id, window_id)` keys reconcile
one-to-one with both geometry and route overlays; there are no duplicate,
missing or extra route keys. Stage0 GPS time is joined to the nearest valid
same-scene RMC fix, with a 2.5-second maximum delta. There is no interpolation
or assignment across a detected continuity break.

| Environment | Scenes | Tasks | Stage2 windows | Located | Unlocated | Valid RMC fixes | Within-component route km |
|---|---:|---:|---:|---:|---:|---:|---:|
| Highway/Open | 2 | 18 | 1,290 | 871 | 419 | 538 | 16.472 |
| Mountain/Valley | 3 | 20 | 1,974 | 1,926 | 48 | 61 | 1.135 |
| Special Reflective | 2 | 16 | 1,656 | 1,565 | 91 | 103 | 1.025 |
| Urban | 6 | 29 | 2,927 | 2,328 | 599 | 160 | 2.233 |
| **Total** | **13** | **83** | **7,847** | **6,690** | **1,157** | **862** | **20.865** |

Located coverage is 85.26%. The 1,157 unlocated selected windows remain in the
overlay: 753 lie within a route discontinuity and 404 are outside the temporal
tolerance. None are silently dropped.

All 862 candidate RMC records were checksum-valid and active with valid dates
and coordinates; aggregate diagnostics found zero invalid checksum, inactive,
malformed, invalid-date, invalid-coordinate, duplicate-time or out-of-order
records. The report does not include record text, coordinates or source paths.

## Segmentation and spatial dependence

Base segmentation uses the predeclared 2.5-second maximum gap and 80 m/s jump
ceiling, yielding 21 continuity components. Threshold sensitivity is
descriptive, not outcome-tuned:

| Sensitivity | Components |
|---|---:|
| Gap 1.5 s / 2.5 s / 5 s (80 m/s jump ceiling) | 30 / 21 / 20 |
| Jump 50 / 80 / 120 m/s (2.5 s gap ceiling) | 25 / 21 / 20 |

The 50/100/250 m candidate grids contain 430/220/95 bins. Of these,
123/76/45 bins respectively contain at least one selected Stage2 window.
Bins are descriptive aggregation candidates, not independent samples.

The spatial summary retains 36 metric-by-lag rows. Every row is
`INSUFFICIENT_SPATIAL_SUPPORT` for a stable correlation-range/effective-local-
unit estimate; no estimate is reported and no independence claim is made.
Window overlap and same-scene runs remain clustered observations.

## Provenance and current boundaries

- Stage2 ledger SHA-256 remains
  `bbb8cac8338194b5527e00812a6547129a58466cc5fdd7db36b8c44bba01e551`.
- Local private outputs are under
  `E:/GNSS_Multipath_Project/dataset_generation_logs/channel_modeling/mainline_1023_geometry_route_20261023T165856Z/`:
  `trajectory_window_overlay.csv`, `route_segments.csv`,
  `spatial_dependence_summary.csv`, and `trajectory_segmentation_audit.json`.
- The route overlay contains precise positions but is ignored by Git. The
  audit JSON and this report contain aggregate results only.
- Task 5 was not changed. At the 2026-10-24 01:39:59 +08 read-only sample,
  its monitor was Ready (last result 0; next run 02:05). The newest report,
  sampled 01:35, still said RUNNING at G06/ch9 but had no stage or valid-
  progress timestamp. Coordinator PID 34916, worker PID 34240 and MATLAB
  PIDs 22304/15280 were present; the RTX 4060 reported 23% utilization.
  E: had 429,108,756,480 bytes free, and no matching System disk/USB event
  appeared in the preceding two hours. This is a point-in-time sample; Task 5
  progress timing remains unverified after the report timestamp.
- Task 5 CIR association and Gate F remain pending. No formal model fit,
  independence claim, or model-validation result is made.

Focused synthetic verification: 31/31 tests passed; compile and diff checks
passed. See the engineering handoff section 97 and the model-preparation spec
addendum for implementation details.
