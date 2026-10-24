# Mainline 10.23 MHz Ephemeris Elevation Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a separate, auditable ephemeris-derived elevation layer for Stage2 windows without mutating measured GSV or trajectory overlays.

**Architecture:** Add a pure Python module for RINEX GPS LNAV parsing/propagation and a small runner that validates a one-scene GSV pilot before producing a full-cohort recovery overlay. Outputs remain local, coordinate-free, timestamped, and create-new.

**Tech Stack:** Python 3 standard library; `unittest`; existing audited geometry and trajectory CSVs.

**Spec:** `docs/superpowers/specs/2026-10-24-mainline-1023-ephemeris-elevation-recovery-design.md`

## Global Constraints

- Preserve exactly 7,847 unique `(run_id, window_id)` rows and all existing measured/missing classifications.
- Keep `GSV_MEASURED` and `EPHEMERIS_DERIVED` distinct; never rewrite old overlays or infer the frozen High/Mid/Low category.
- Derive only using a validated same-scene receiver position and healthy, exact-PRN broadcast ephemeris within two hours of toe.
- Never read raw IQ or MAT/HDF5/CIR payloads; never launch GNSS-SDR; do not touch Task 5.
- Do not publish coordinates or raw NMEA sentences; do not modify the Stage2 ledger, Task 6, Task 5, manifest, summary, or prior overlays.

## Review Focus

- GPS week rollover and UTC-to-GPS conversion: test across week boundary and leap offset.
- Stale/unhealthy or wrong-PRN ephemerides: reject rather than silently propagate.
- Duplicate or mismatched `(run_id, window_id, scene_id, PRN)` inputs: fail closed.
- GSV-measured rows: never replace them with computed elevations.
- Existing output namespace or incomplete input overlay: refuse without writing.

---

### Task 1: GPS LNAV ephemeris parser and propagation

**Files:**
- Create: `scripts/channel_modeling/mainline_rinex_ephemeris_geometry.py`
- Test: `scripts/channel_modeling/tests/test_mainline_rinex_ephemeris_geometry.py`

**Interfaces:**
- `parse_gps_lnav_records(text: str) -> list[GpsEphemeris]`
- `select_ephemeris(records, prn, observation_utc, *, max_toe_age_s=7200) -> GpsEphemeris | None`
- `satellite_elevation_deg(ephemeris, observation_utc, latitude_deg, longitude_deg, height_m=0.0) -> float`

- [x] Write failing synthetic tests for fixed-column RINEX 3 parsing, D exponents, health filtering, wrong PRN, toe age boundary, GPS week rollover, and a deterministic propagated elevation.
- [x] Run the focused test and verify it fails because the new module is absent.
- [x] Implement only the parser, record selection, GPS broadcast orbit propagation, ECEF/ENU transform, and explicit input validation.
- [x] Re-run the focused test and verify PASS.

### Task 2: Coordinate-free overlay runner and tests

**Files:**
- Create: `scripts/channel_modeling/run_mainline_rinex_ephemeris_recovery.py`
- Modify: `scripts/channel_modeling/tests/test_mainline_rinex_ephemeris_geometry.py`

**Interfaces:**
- CLI `--project-root`, `--geometry-overlay`, `--trajectory-overlay`, `--output-dir`, and pilot-only `--validate-scene`.
- Pilot audit reports agreement against existing GSV on matched GSV+position rows.
- Full run emits one row per old geometry identity, using GSV first and ephemeris only where GSV is missing, position is valid, and ephemeris passes selection.

- [x] Add failing tests for exact-key join/reconciliation, GSV precedence, derived-only missing rows, explicit no-position/no-ephemeris reasons, no coordinate output, source provenance, and create-new output semantics.
- [x] Run the focused tests and verify expected failures.
- [x] Implement the runner using only existing small CSV/NMEA/RINEX files; never open prohibited payloads.
- [x] Run focused tests and verify PASS.

### Task 3: Pilot, full cohort, report, and delivery

**Files:**
- Runtime only: `E:\GNSS_Multipath_Project\dataset_generation_logs\channel_modeling\mainline_1023_ephemeris_recovery_<UTC>\`
- Git: the two new Python files, their test, this spec/plan, and a sanitized aggregate report.

- [x] Run the pilot for `F1023_V120_D0121_P2`; review its audit before any full run.
- [x] After pilot acceptance, run the full 13-scene overlay once to a new namespace.
- [x] Verify 7,847 exact unique identities; reconcile all existing GSV and position counts; summarize measured, derived, and still-missing elevations separately by scene/environment.
- [x] Verify no coordinate/raw sentence appears in the output audit or Git artifacts; verify old overlays and Stage2 ledger remain unchanged. Task 5 was only sampled read-only (batch/G25 tasks Running, monitor Ready); no release content, stage, process control, or output changes were made.
- [x] Run the new focused tests after final edits. Commit only this scope and push to the existing Draft PR branch without merging (delivery step remains pending until completed).
