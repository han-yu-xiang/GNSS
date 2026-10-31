# Mainline Stage2 measured-elevation and route audit

Audit date: 2026-10-24 (local project workspace)

## Scope and safeguards

This Task 7 audit used the frozen 83-task cohort and existing Stage2 ledger.
It did not run SAGE, MATLAB or CIR production, and did not read CIR/HDF5, MAT,
or raw-IQ payloads. The GSV phase read only the RINEX first-record date and GPS
PRN inventory; it did not parse navigation ephemerides or recompute elevation.
The route phase re-verified all 205 input pins and read RINEX by hash/size only.
Precise route coordinates and source-record paths are confined to the ignored
local output namespace; this report contains aggregate values only.

## Measured GSV elevation overlay

| Quantity | Audited value |
|---|---:|
| Frozen cohort tasks / scenes | 83 / 13 |
| Stage0-valid windows | 285,752 |
| Stage2 paths / selected windows | 16,761 / 7,847 |
| Same-scene, same-PRN measured GSV matches | 5,128 |
| Explicitly missing GSV matches | 2,719 |

Elevation is sourced only from checksum-valid, timestamped GPS GSV records.
The nine frozen missing-elevation task classifications remain `MISSING`; 728
selected windows in those tasks have no matching target-PRN GSV observation.
No values were imputed or derived from orbit calculations.

## Route overlay and coverage

The corrected route runner verified the GSV audit's 205 input pins, loaded
code pins and exact cohort and ledger identities. The 7,847 Stage2
`(run_id, window_id)` keys reconcile
one-to-one with both geometry and route overlays; there are no duplicate,
missing or extra route keys. Stage0 GPS time is joined to the nearest valid
same-scene RMC fix only within observed component coverage, with a 2.5-second
maximum delta. There is no endpoint extrapolation, interpolation, or
assignment across a detected continuity break. Rejected RMC records create
continuity barriers; this cohort contained no rejected RMC records.

| Environment | Scenes | Tasks | Stage2 windows | Located | Unlocated | Valid RMC fixes | Within-component route km |
|---|---:|---:|---:|---:|---:|---:|---:|
| Highway/Open | 2 | 18 | 1,290 | 732 | 558 | 538 | 16.472 |
| Mountain/Valley | 3 | 20 | 1,974 | 1,480 | 494 | 61 | 1.135 |
| Special Reflective | 2 | 16 | 1,656 | 1,436 | 220 | 103 | 1.025 |
| Urban | 6 | 29 | 2,927 | 1,892 | 1,035 | 160 | 2.233 |
| **Total** | **13** | **83** | **7,847** | **5,540** | **2,307** | **862** | **20.865** |

Located coverage is 70.60%. The 2,307 unlocated selected windows remain in the
overlay: 753 lie within a route discontinuity and 1,554 are outside observed
route coverage. None are silently dropped. The lower count relative to the
first audit is the intended result of removing endpoint extrapolation.

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
121/75/44 bins respectively contain at least one located Stage2 window.
Bins are descriptive aggregation candidates, not independent samples.

Each continuity component is normalized by its own metric variance; normalized
lag estimates are pair-count weighted within run, runs are equally weighted
within scene, and scenes are equally weighted across the cohort. The spatial
summary retains 36 metric-by-lag rows. Every row is
`INSUFFICIENT_SPATIAL_SUPPORT` for a stable correlation-range/effective-local-
unit estimate; no estimate is reported and no independence claim is made.
Window overlap and same-scene runs remain clustered observations.

## Provenance and current boundaries

- Stage2 ledger SHA-256 remains
  `bbb8cac8338194b5527e00812a6547129a58466cc5fdd7db36b8c44bba01e551`.
- Corrected local private outputs are under
  `E:/GNSS_Multipath_Project/dataset_generation_logs/channel_modeling/mainline_1023_geometry_route_20261023T180857Z/`:
  `trajectory_window_overlay.csv`, `route_segments.csv`,
  `spatial_dependence_summary.csv`, and `trajectory_segmentation_audit.json`.
- The precise-coordinate route overlay remains local and Git-ignored; both
  runners now reject any output path outside a timestamped ignored private
  namespace. Sanitized audit JSON and this report contain aggregate results.
- Task 5 was not changed. At the 2026-10-24 02:07 +08 read-only sample, its
  monitor was Ready; its latest report at 02:05 still said RUNNING at G06/ch9,
  with latest valid progress at 2026-10-23 12:39:17 UTC (no stage/current
  progress delta verified). Coordinator/worker PIDs 34916/34240 and MATLAB
  PIDs 22304/15280 were present. E: had 428,242,108,416 bytes free; no matching
  System disk/USB event appeared in the preceding two hours. Task 5 was left
  untouched; this is a point-in-time sample and not evidence of progress.
- Task 5 CIR association and Gate F remain pending. No formal model fit,
  independence claim, or model-validation result is made.

Focused synthetic verification after the correction: 67/67 geometry and route
tests passed. All 13 GPS time-origin residuals were VERIFIED; maximum residual
was 0.01152 s against a fail-closed 0.5 s limit. There were no conflicting or
duplicate GSV epochs and no rejected RMC records. See engineering handoff
section 97 and the model-preparation spec addendum for corrected results.
