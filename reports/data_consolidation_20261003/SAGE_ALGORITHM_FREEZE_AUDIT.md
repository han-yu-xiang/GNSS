# Frozen SAGE algorithm audit

Audit date: 2026-10-03  
Scope: static source, metadata, logs, and filesystem metadata only. No MATLAB, SAGE, GNSS-SDR, production batch, or raw-IQ content was read or executed.

## Verdict

The frozen production entrypoint is present and its SHA-256 matches the freeze record. It is the authoritative SAGE implementation for this rerun matrix.

- Status: FROZEN_VALIDATED_EQUIVALENT_CONFIRMED
- Entrypoint: E:\GNSS_Multipath_Project\scripts\sage_pipeline\run_nav_sage_pipeline.m
- Expected SHA-256: bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c
- Observed SHA-256: BFFC123C97AF77F0A797F417D3866E9A34FEAB7729C5C1575352F53BC3571B9C
- Match: YES
- Frozen supported sample rate: 10,230,000 Hz
- 20,460,000 Hz input: unsupported by the frozen SAGE support gate; do not infer resampling support.

The audited implementation includes Stage0 through Stage4, local Stage1–Stage4 execution, Stage1 fast scan, Stage2 fractional SAGE for L=1..4, Stage3 persistence, and Stage4 joint 100 ms processing. This report freezes identity and documents the input contract; it does not run or modify the algorithm.

## Hard input contract established from current source

1. Explicit PRN and TrackingChannel are required.
2. Scene metadata must provide scene identity, signal.sample_rate_hz, and raw_iq.path; the raw file must exist.
3. Required scene folders: gnss_sdr, navigation, trajectory, and satellite.
4. Required channel-specific inputs: exactly matching tracking MAT and telemetry DAT files.
5. Exactly one RINEX NAV file matching *.26N is required for presence. The estimator does not parse that RINEX NAV file in this path.
6. An NMEA file is required to exist; valid RMC parsing is optional in the current code path.
7. Satellite CSVs are enumerated, but the current hard gate does not assert nonempty CSV content.
8. The raw reader is little-endian signed int16 with interleaved I/Q. Seeking uses four bytes per complex sample; the code reads the raw samples when the pipeline runs. This audit did not read them.

Not hard-gated by this entrypoint: GNSS-SDR config/log/receipt/QA, observables, PVT, RINEX OBS, and prior SAGE outputs. Those remain important provenance and audit evidence, not substitutes for the channel-specific hard inputs above.

## Operational implications for a future rerun

- The entrypoint's default checkpoint/resume behavior can reuse outputs. A future approved run should target a new output namespace and explicitly disable resume (Resume=false), then record the exact source SHA and command/config provenance.
- Use only the PRN/channel pairs in the readiness CSV, not filename-derived PRN guesses.
- The code-derived contract is a readiness check, not a claim that any SAGE rerun has occurred.
- Do not archive current results until per-row paper-reference review is complete and the user separately approves the move.

## Alternate implementations observed; not selected

Static inventory found other historical/diagnostic entrypoints or support files. They are not authority for the frozen production run and must not be substituted without a deliberate freeze change.

| Variant | SHA-256 evidence | Audit disposition |
|---|---|---|
| G06 legacy entry | DF1C9ABB...A5310F91 | Historical, not selected |
| Shared SAGE core | E3E61C37...CE7430C | Support module |
| Shared configuration | AC06AD...BED1319 | Support/config |
| Rain entry and stages | ED8E6820...D86FEC27; D46CE7FE...B8F69976 | Separate historical/model workflow |
| Regression recovery | F62AA999...BF8A041 | Recovery diagnostic |
| Recovery copy | 95F608AC...DF838DEF0 | Differs; not authoritative |
| Diagnostic replay | AE4E6B02...823CCA9 | Diagnostic only |

The complete static inventory did not identify a second production substitute with the frozen entrypoint's authority.

## Evidence limits

This is an identity and source-contract audit. It does not establish that every possible runtime dependency is available on a future machine, does not validate new outputs, and does not certify scene-level scientific quality. The working tree already contained user changes before these reports were created; those changes were preserved.

