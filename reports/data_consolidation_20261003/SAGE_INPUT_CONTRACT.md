# SAGE input contract for the frozen rerun

This is a source-derived preflight contract for E:\GNSS_Multipath_Project\scripts\sage_pipeline\run_nav_sage_pipeline.m. It is not a run instruction and no SAGE/MATLAB/GNSS-SDR process was launched.

## Required per scene

- metadata.json with scene identity, signal.sample_rate_hz, and raw_iq.path.
- Existing raw IQ file at the metadata-declared path.
- Existing gnss_sdr, navigation, trajectory, and satellite directories.
- One explicitly selected PRN and one explicitly selected TrackingChannel.
- The exact tracking channel MAT file and telemetry channel DAT file for that selection.
- Exactly one navigation RINEX matching *.26N (presence gate only; not parsed by this estimator path).
- At least one NMEA file at the expected scene path (existence gate; parsing can be optional).

## Format and rate

- Raw sample format: little-endian signed int16, interleaved I then Q.
- Complex sample offset: four bytes per sample.
- Frozen algorithm support gate: 10,230,000 Hz.
- The 20,460,000 Hz datasets are not currently SAGE-ready under this frozen entrypoint, even where GNSS-SDR PRN/channel inputs are complete. Do not silently downsample or reinterpret.

## Not a hard input gate in the current entrypoint

GNSS-SDR config/log, execution receipt, independent QA, observables, PVT, RINEX OBS, previous SAGE outputs, and nonempty satellite-CSV content are not required by this entrypoint's current hard checks. Keep these as provenance, QA, and scientific review materials. A successful hard-input gate alone is not a scientific validation.

## Safe future-run settings (recommendation only)

Use the exact PRN/channel mapping in the readiness matrix; assign a new output namespace; explicitly set Resume=false to prevent reuse of prior checkpoints; record command, source SHA-256, config, start/end times, and output manifest. Any actual execution requires a separate concrete user task.

