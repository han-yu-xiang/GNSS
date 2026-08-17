# GNSS Darkroom Channel Emulation Engineering Handoff

## Current branch decision

As of 2026-08-17:

```text
SHARED_CORE_REFACTOR_FOR_RAIN = FROZEN
STANDALONE_RAIN_PIPELINE = ACTIVE_IMPLEMENTATION
RAIN_SAGE_EXECUTION = NOT_STARTED
RAIN_G24_PREFLIGHT = NOT_STARTED
```

The standalone route was selected because repeated shared-core extraction
and MATLAB syntax failures created more production risk than Rain-MVP value.
The shared-core files and all failure artifacts remain immutable historical
engineering evidence.

## Production safety state

The recorded pre-refactor validated production hash is
`5ff00366f2d71eff7945418ce484b0fedb7199f1144c2db2fb18268fe5b4b0ab`.
The current `scripts/sage_pipeline/run_nav_sage_pipeline.m` hash is
`95f608acb9c7920fcef88855c866fb74465e1a080893b1ea276ab00df838def0`.
No traceable backup or historical source bytes matching the former hash were
found in the project or on `E:\`. Consequently:

```text
PRODUCTION_PIPELINE_CURRENT_STATE = MODIFIED_BY_REFACTOR
PRODUCTION_PIPELINE_RAIN_BRANCH_CHANGES = NOT_CLEARABLE
```

No untraceable manual restoration was attempted. Production SAGE remains
blocked until a validated source can be recovered or supplied.

## Standalone Rain implementation

Rain-local files are:

- `scripts/sage_pipeline/rain/run_rain_sage_stage1_stage4.m`
- `scripts/sage_pipeline/rain/default_rain_sage_configuration.m`
- `scripts/sage_pipeline/rain/compute_rain_doppler_bound.m`
- `scripts/sage_pipeline/rain/run_rain_sage_pipeline.m`
- `scripts/sage_pipeline/rain/build_rain_stage0.m`
- `scripts/sage_pipeline/rain/run_rain_matlab_syntax_smoke.m`

The Stage1–Stage4 body is copied from the extracted production source
lineage. The source-level comparison is recorded in
`dataset_generation_logs/darkroom_channel_emulation/rain_standalone_algorithm_equivalence.md`.
The comparison reports no algorithm difference relative to the extracted
body; it does not substitute for a validated production-byte restoration.

The only allowed Rain differences are:

- tracking + telemetry input preparation without NMEA/PVT/RINEX/trajectory/
  geometry;
- explicit unavailable speed/geometry values, never fabricated values;
- local copied configuration and no-speed Doppler fallback;
- `rain_sage_v1` output namespace;
- new-only `Resume=false` behavior.

Stage1/Stage2/Stage3/Stage4 thresholds, grids, model-order rules, persistence,
joint validity, and confirmed-path criterion are unchanged.

## Syntax-smoke state

The old smoke artifact is
`dataset_generation_logs/darkroom_channel_emulation/matlab_syntax_smoke_20260817.log`.
It lacks per-file diagnostic details, so the three old FAIL entries cannot be
classified as parser errors versus warnings from that artifact alone. The
generic helper now emits file, line, column, severity, ID, and message; the
Rain-only entry is `run_rain_matlab_syntax_smoke.m`. MATLAB has not been run
by Codex.

## Mandatory gates before Rain execution

1. Recover or restore a traceable validated production source.
2. Confirm the standalone algorithm-equivalence audit has no algorithm
   difference.
3. Run Rain-only MATLAB syntax smoke as a normal Windows user and require
   `MATLAB_SYNTAX_SMOKE=PASS`.
4. Run one normal-user G24 `PreflightOnly=true` check.
5. Only after Commander approval, create one new-only Rain request and run
   one Rain task.

No G24 preflight, Rain SAGE, production SAGE, batch, raw-IQ processing, or
20.46 MHz task was run for this handoff update.

## Emergency exact production-source recovery audit (Blocked, 2026-08-17)

The Commander-required historical production source is exactly:

```text
scripts/sage_pipeline/run_nav_sage_pipeline.m
SHA-256 = 5ff00366f2d71eff7945418ce484b0fedb7199f1144c2db2fb18268fe5b4b0ab
```

The current production entry was rehashed as
`95f608acb9c7920fcef88855c866fb74465e1a080893b1ea276ab00df838def0`.
Before searching, it was preserved byte-for-byte and marked read-only at:

```text
dataset_generation_logs/darkroom_channel_emulation/production_pipeline_recovery_20260817/run_nav_sage_pipeline.modified_by_shared_core_refactor.m
```

The preserved copy and current source both hash to
`95f608acb9c7920fcef88855c866fb74465e1a080893b1ea276ab00df838def0`.
The recovery ledger is
`dataset_generation_logs/darkroom_channel_emulation/production_pipeline_recovery_candidates.csv`
(SHA-256=`c5ea97e258122a408a9c070b34189bb587c138dae4c6f50531e304f1d709b3e0`).

The project and E:\ same-name trees, relevant archives/backups, project
provenance/logs, Git history/object recovery, VS Code History, temporary and
MATLAB autosave locations, OneDrive, File History, and Recycle Bin were
checked read-only. The project and E:\ have no Git repository; status,
history, reflog, unreachable-object, and lost-found checks all failed closed
with “not a git repository”. The only project archive was `docs/paper_draft.zip`
and it contained no relevant MATLAB source. The target hash appeared only in
provenance text, not in recoverable source bytes.

```text
CURRENT_MODIFIED_COPY_PRESERVED=YES
PRODUCTION_VALIDATED_SOURCE_RECOVERY=BLOCKED
EXACT_HASH_NOT_FOUND=YES
PRODUCTION_PIPELINE_CURRENT_SHA256=95f608acb9c7920fcef88855c866fb74465e1a080893b1ea276ab00df838def0
PRODUCTION_PIPELINE_FROZEN=NO
PRODUCTION_SAGE_PIPELINE_POLICY=FROZEN
FROZEN_TARGET_SHA256=5ff00366f2d71eff7945418ce484b0fedb7199f1144c2db2fb18268fe5b4b0ab
```

No manual reconstruction, shared-core copy-back, or production-file overwrite
was attempted. `PRODUCTION_SAGE_PIPELINE_FREEZE.md` was not created because
the exact source was not found. Rain files remained under
`scripts/sage_pipeline/rain/` and did not touch the production entry. The
user-reported normal-user Rain syntax smoke PASS/exit code 0 is retained but
was not rerun; `RAIN_G24_PREFLIGHT=NOT_RUN` remains in force. The only next
action is Commander direction or a traceable exact source; no Rain or
production execution is permitted before recovery.
