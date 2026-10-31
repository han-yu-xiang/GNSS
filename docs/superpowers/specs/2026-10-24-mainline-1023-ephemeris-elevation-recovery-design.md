# Mainline 10.23 MHz Ephemeris-Derived Elevation Recovery

## Intent

Audit the existing 13-scene GNSS-SDR products and recover satellite elevation only where the historical broadcast ephemeris and an already-validated receiver position jointly support a defensible computation. This is a new, separate evidence layer; it does not revise the receiver-measured GSV overlay or its missing reasons.

## Goals and non-goals

- Preserve all 7,847 unique Stage2 `(run_id, window_id)` identities in one new local overlay.
- Retain existing GSV values as `GSV_MEASURED`; add only independently computed values as `EPHEMERIS_DERIVED`.
- Derive only for windows with a valid same-scene trajectory position and a healthy same-scene GPS LNAV record within the conservative two-hour `|t - toe|` bound.
- Validate the propagation against windows with both a GSV measurement and validated position before applying it to any missing-elevation window.
- Preserve the existing position overlay, Stage2 ledger, Task 5 CIR process/release/outputs, and all historical artifacts.
- Do not read raw IQ or MAT/HDF5/CIR payloads; do not launch GNSS-SDR; do not interpolate/extrapolate receiver positions; do not convert computed values into measured GSV or frozen elevation classes.
- Do not publish exact receiver coordinates, raw NMEA sentences, or raw receiver telemetry in Git/PR.

## Approaches considered

1. Keep the existing GSV-only policy. This preserves the original Task 7 draft exactly, but leaves a demonstrably testable recovery opportunity unused despite the Commander’s new explicit authorization.
2. Add a separately named ephemeris-derived layer with strict source/status separation and GSV cross-validation. This preserves the old measured evidence and makes the new provenance explicit; selected because it fulfills the new recovery request without overwriting prior results.
3. Replace the old geometry overlay with computed values. Rejected because it would erase the distinction between receiver observations and model-derived geometry and mutate a frozen prior result.

## Method

- Parse RINEX GPS navigation records without opening any MAT/HDF5 or raw signal payload.
- Convert the already-audited Stage2 UTC time to GPS time using the applicable GPS-UTC offset; select only a healthy ephemeris for the exact GPS PRN and scene, with `|t-toe| <= 7200 s`.
- Propagate GPS broadcast Kepler elements at signal transmit time using the GPS LNAV equations and Earth-rotation correction; compute topocentric elevation from the already validated same-scene position. Use ellipsoidal height only when an exact-time valid GGA height is available; otherwise record a zero-height assumption explicitly.
- For the validation pilot, compare computed elevation to the existing integer-degree GSV on rows where both existing GSV and position evidence are valid. Report signed bias, MAE, P95 absolute error, maximum absolute error, and count exceeding 1 degree.
- For recovery, leave GSV-matched rows’ measured source intact. Derive only for GSV-missing rows with a position match and a qualifying broadcast record. Every other row remains explicitly missing with a reason.
- Write only to a create-new, timestamped directory under `dataset_generation_logs/channel_modeling/`; include a coordinate-free per-scene summary and a provenance audit with input hashes, counts, method, and assumptions.

## Acceptance

- Synthetic tests cover RINEX parsing, GPS week/time handling, healthy/expired ephemeris selection, orbital propagation, GSV/position/status separation, identity preservation, and refusing to overwrite an existing namespace.
- The pilot is run first on `F1023_V120_D0121_P2` and must reproduce the previously observed high agreement (MAE below 0.5 degrees; no absolute error above 1 degree) before the full cohort overlay is created.
- The final overlay contains exactly 7,847 unique `(run_id, window_id)` keys and reconciles to both old overlays; no row or MPC is dropped.
- Summary separately reports measured GSV, ephemeris-derived, still-missing elevation, old position coverage, and joint elevation-position support. No position recovery is claimed unless independently supported by additional epochs; RINEX OBS is not treated as a receiver position output by itself.
- No GNSS-SDR rerun is authorized by this design; if existing evidence cannot support a reliable result, retain missing status and provide a scene-specific recommendation only.
