# Mainline raw IQ → GNSS-SDR → SAGE rerun readiness

Audit date: 2026-10-03. This is a static inventory and readiness matrix only. No raw-IQ contents were opened; no MATLAB, GNSS-SDR, SAGE, or batch was run.

## Summary

- Raw datasets inventoried: 19 (13 at 10.23 MHz; 6 at 20.46 MHz).
- PRN/channel mappings from GNSS-SDR NAV-message logs: 130.
- GNSS-SDR channel hard inputs present: 130/130; 0 incomplete.
- Ready for frozen SAGE rate gate and channel-input gate: 89.
- Channel inputs complete but sample rate unsupported by frozen SAGE: 41.
- Existing SAGE namespaces inventoried: 78; 1649 files, 229230888 bytes.
- Existing namespace archive candidates that meet raw + GNSS-SDR pair + frozen-rate regenerability checks: 77; no move is authorized by this report.

## Readiness distinctions

A row marked READY_FOR_FROZEN_SAGE means the static hard-input checks passed and the sample rate matches the frozen entrypoint gate. It is not scientific validation and is not permission to execute. The 41 20.46 MHz rows have complete channel inputs but remain unsupported by the frozen algorithm. No row was found with missing GNSS-SDR tracking/telemetry files.

PRN/channel mappings were derived from GNSS-SDR NAV-message log evidence intersected with channel tracking and telemetry files. They were not guessed from filenames. Seven mapped pairs lack a tracking-start line; the NAV-message log directly identifies the PRN/channel and both channel files exist, but these rows are explicitly flagged for log review.

Scene inventories contain raw/metadata/config, GNSS-SDR outputs and channel files, navigation/RINEX NAV, trajectory/NMEA, satellite context, and observables/PVT directories. The inventory reports SUCCESS execution evidence, but an independent per-task QA artifact was not located. Treat this as execution evidence only.

## Planned rerun controls (not executed)

1. Freeze and record the exact entrypoint SHA in SAGE_ALGORITHM_FREEZE_AUDIT.md.
2. Select only the 89 supported rows in mainline_prn_channel_sage_readiness.csv.
3. Use a new output namespace and explicitly set Resume=false; do not reuse existing result folders or checkpoints.
4. Record the selected pair, raw/metadata provenance, GNSS-SDR source log, config, invocation, and output manifest.
5. Run a small user-approved validation first, then expand only after inspecting its outputs and QA. This report itself does not authorize or launch that run.

## Existing result archive assessment

All 78 existing SAGE namespaces map to present 10.23 MHz raw datasets and complete GNSS-SDR PRN/channel inputs, so each is marked YES_REGENERABLE / ARCHIVE_CANDIDATE in mainline_existing_sage_archive_manifest.csv. This establishes regenerability under the frozen source contract, not that the old results are scientifically invalid or disposable. The paper-reference field is deliberately REVIEW_REQUIRED_BEFORE_MOVE for every row. Destination collisions must be checked at execution time. Preserve the namespace tree and filenames.

Summary by source sample rate: 10230000 Hz: 13 datasets; 20460000 Hz: 6 datasets. SAGE namespace inventory total: 229230888 bytes.

Darkroom context cross-check (from the same audit bundle): 0919 v2 contains 253 files / 3,054,921,074 bytes and the current handoff records QA 48/48 PASS (31 with position, 17 without position); 0/48 are SAGE-ready. The formal 48-table directory live stat is 14,151,659,699 bytes; an older handoff records 14,151,548,683 bytes, a 111,016-byte discrepancy. The static hash audit covered 35 generator/model dependencies; 31 declared hashes matched (of 31 declared hashes). Keep final inputs and dependencies in place.

