# Stage4 path-parameter derivation — 2026-08-25

## Status

`CHANNEL_PARAMETER_DERIVATION = COMPLETED_WITH_EXCLUSIONS`

This versioned derivation reads only the independently QA-passed modeling-context
alignment overlay. It does not read raw IQ or Stage4 MAT payloads, and it does
not run MATLAB, SAGE, batch execution, or a stochastic channel-model fit.

## Derived quantities

- Path-level excess delay in seconds: `excess_delay_samples / 10230000`.
- Path-level excess path length in meters: `excess_delay_s * 299792458`.
- Signed relative Doppler: copied from the Stage4 `doppler_offset_hz` field.
- Relative power: copied from the Stage4 `mean_relative_power_db` source field.
- Event and group tables contain descriptive counts, medians, minima and maxima
  only; no fitted distribution is produced.
- Elevation bands use lower-inclusive intervals: LOW `[0,30)`, MID `[30,60)`,
  HIGH `[60,90]` degrees.

## Counts

- Environment-ready confirmed paths: 100.
- Elevation-ready confirmed paths: 84.
- Confirmed events represented by the environment-ready paths: 94.
- Environment groups: 4; elevation groups: 3.
- Explicit elevation exclusions: 16 paths retained for environment
  summaries but excluded from elevation-group summaries.

## Deliberately not derived

`RMS_DELAY_SPREAD`, `DOPPLER_SPREAD`, `RICEAN_K_FACTOR`, and `PATH_LIFETIME`
remain `NOT_DERIVED` in this version because the current frozen audit schema does
not provide a validated complete power/phase path set, a temporal path identity,
or a separately approved statistical definition for those quantities.

## Provenance and execution record

- Source alignment partition: `dataset/multipath_event_database/v1/partitions/alignment_id=alignment_20260825_tow_geometry_scene_v1/`.
- Alignment QA status required: `PASS`.
- Raw IQ read: no.
- MATLAB/SAGE/batch started: no.
- Existing SAGE artifacts, requests, manifest, inventory and alignment tables
  modified: no.
- Statistical channel modeling started: no.
