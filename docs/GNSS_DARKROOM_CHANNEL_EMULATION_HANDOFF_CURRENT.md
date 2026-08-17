# GNSS Darkroom Channel Emulation Engineering Handoff

## Current branch decision

As of 2026-08-18:

```text
SHARED_CORE_REFACTOR_FOR_RAIN = FROZEN
STANDALONE_RAIN_PIPELINE = ACTIVE_IMPLEMENTATION
PRODUCTION_PIPELINE_FROZEN = YES
VALIDATED_EQUIVALENT_RECOVERY = PASS
RAIN_SAGE_EXECUTION = NOT_STARTED
RAIN_G24_PREFLIGHT = NOT_STARTED
```

The standalone route was selected because repeated shared-core extraction
and MATLAB syntax failures created more production risk than Rain-MVP value.
The shared-core files and all failure artifacts remain immutable historical
engineering evidence.

## Production safety state

The recorded pre-refactor validated production hash is
`5ff00366f2d71eff7945418ce484b0fedb7199f1144c2db2fb18268fe5b4b0ab` and
remains unrecovered. The validated-equivalent frozen
`scripts/sage_pipeline/run_nav_sage_pipeline.m` hash is
`bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c`.
The normal-user G28 comparison-only regression passed against the preserved
actual output, so the current state is:

```text
EXACT_SOURCE_RECOVERY = BLOCKED
VALIDATED_EQUIVALENT_RECOVERY = PASS
PRODUCTION_PIPELINE_CURRENT_STATE = VALIDATED_EQUIVALENT_FROZEN
PRODUCTION_PIPELINE_RAIN_BRANCH_CHANGES = ISOLATED
```

No untraceable manual restoration was attempted. Production is frozen at the
validated-equivalent source; exact historical-source recovery remains
blocked and must not be represented as successful.

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

## Validated-equivalent production recovery route (Implemented + static Validated; MATLAB pending, 2026-08-17)

The exact historical source remains unrecoverable:

```text
EXACT_HISTORICAL_SOURCE_RECOVERY=BLOCKED
HISTORICAL_TARGET_SHA256=5ff00366f2d71eff7945418ce484b0fedb7199f1144c2db2fb18268fe5b4b0ab
```

Commander therefore switched to `VALIDATED_EQUIVALENT_PRODUCTION_RECOVERY=ACTIVE`.
The production entry was mechanically restored as a standalone monolithic
candidate, without new thresholds, grids, tuning, Stage semantics, or a new
algorithm. Candidate:

```text
scripts/sage_pipeline/run_nav_sage_pipeline.m
SHA256=f1a16ceea6bcdafd46a85bce478d18e96f4dcd19e9bcb3991fb35b867e2b2088
```

It contains local Stage1–Stage4 and local configuration/Doppler helpers and no
dependency on `scripts/sage_pipeline/core/`. The shared-core source and
`run_shared_core_regression.m` remain frozen audit evidence, not the final
production route. The detailed classification is in
`dataset_generation_logs/darkroom_channel_emulation/production_refactor_damage_audit.md`.

The synchronized provenance manifest is
`dataset_generation_logs/darkroom_channel_emulation/rain_provenance_manifest.json`
(SHA256=`2e012111e2ebe56c7c1118656c0f251b663c24f6e27970168b921143b4ab8705`).

P0 created a local Git checkpoint before restoration edits:

```text
COMMIT=0f9726e8be94af19064b2ac44cd007a61048730c
MESSAGE=checkpoint: preserve pre-recovery GNSS SAGE source state
```

The new production-only syntax smoke is
`scripts/sage_pipeline/regression/run_production_matlab_syntax_smoke.m`
(SHA256=`8b4de75ae9b84fa637e7896763bd24dd70d75e889e6c8c0fd1068a1f3d97ced3`).
The protected G28 replay harness is
`scripts/sage_pipeline/regression/run_production_recovery_regression.m`
(SHA256=`3cb5bb87d3cb058f63d444bd2d3eca0cb593b527498be0e568eecc634849991c`).
It fixes G28/ch1/10.23 MHz, passes `Resume=false`, regenerates Stage0 from a
fresh isolated non-raw input tree, compares Stage0 and Stage1–Stage4 outputs
with absolute tolerance `1e-9` and relative tolerance `1e-12`, and never writes
under the protected baseline `scenes/F1023_V70_D0117_P2/sage_results/nav_sage_v2/G28`.

Python `py_compile` and the compiled local Python static/unit suites passed
`148/148`. This does not validate MATLAB syntax or numerical equivalence. The
current gates are:

```text
VALIDATED_EQUIVALENT_RECOVERY=READY_FOR_MATLAB_VALIDATION
PRODUCTION_MATLAB_SYNTAX_SMOKE=NOT_RUN
G28_NUMERICAL_REGRESSION=NOT_RUN
PRODUCTION_PIPELINE_FROZEN=NO
RAIN_G24_PREFLIGHT=NOT_RUN
RAIN_SAGE_EXECUTION=NOT_STARTED
```

Do not create the production freeze document, commit/tag the candidate, run
G28, run Rain/G24, or resume production until the normal Windows user
`TJ-CHANNEL\\Jing_` has run the syntax smoke and, only after a syntax PASS, the
G28 numerical replay. Rain remains paused and no VTC/Paper state is changed.

## Read-only GNSS-SDR weather-effect MVP (Completed + Validated, 2026-08-17)

- The existing standardized GNSS-SDR outputs for F1023_clear, F1023_midrain, and F1023_heavyrain were audited without opening raw IQ content, rerunning GNSS-SDR, invoking the MATLAB executable, or running SAGE.
- Analysis tool: `scripts/analysis/rain_gnss_sdr/audit_rain_gnss_sdr_mvp.py`, SHA-256 `7f4798f693fc1283d1d1a288c9336a6db0806ca8c7167791495a5f95d755391f`.
- Meeting package: `dataset_generation_logs/darkroom_channel_emulation/gnss_sdr_weather_mvp_20260817/`, containing the summary, scene/PRN metrics, matched G24 comparison, field inventory, provenance, meeting brief, and four figures. Superseded self-generated diagnostic copies remain retained separately.
- Validated mappings are clear ch3/G29, ch8/G13, ch10/G24, ch11/G12; midrain ch8/G24, ch9/G20; heavyrain ch1/G02, ch4/G31, ch7/G01. Only clear G24/ch10 versus midrain G24/ch8 is a same-PRN comparison.
- The evidence is receiver-level: C/N0, tracking validity and duration, lock continuity, robust Doppler/code-frequency variation, telemetry/CRC, and observables. Trajectory/geometry are unavailable for this MVP, and no rain attenuation law, weather-conditioned multipath law, or statistical model is claimed.
- The actual pre-existing production source hash was `f1a16ceea6bcdafd46a85bce478d18e96f4dcd19e9bcb3991fb35b867e2b2088`; the Commander request cited `95f608acb9c7920fcef88855c866fb74465e1a080893b1ea276ab00df838def`. The discrepancy was recorded without changing the source.
- Darkroom status: `Completed + Validated` for the read-only weather-effect MVP. Rain/G24 SAGE remains paused pending the existing protected MATLAB syntax and G28 replay gates.

## G28 recovery packaging fix (Implemented + static Validated; MATLAB pending, 2026-08-17)

- The preserved G28 recovery run reached Stage4 and failed only while constructing the returned result container. Stage4 numerical work had already written its CSV/MAT outputs; classify it as `PRODUCTION_RECOVERY_RESULT_PACKAGING_ERROR`, not a SAGE algorithm regression.
- The MATLAB `struct` error refers to input argument positions 20 (`jointFits`) and 8 (`stage2Fits`), both non-scalar cell values. It does not prove literal array lengths 20 and 8. The fix uses scalar struct field assignment and an `isscalar(result)` assertion in the production entry.
- Changed only `scripts/sage_pipeline/run_nav_sage_pipeline.m` and the recovery harness/test guard. No Rain source, shared-core audit source, baseline G28 artifact, or Stage numerical logic was changed.
- Fix report: `dataset_generation_logs/darkroom_channel_emulation/production_recovery_result_packaging_fix_20260817/result_packaging_fix_report.md` (SHA-256=`d9d58cea4eeb53d8911e2206ccf206650a35b359951489a59cb090868bc6567b`). Relevant static tests are `20/20 PASS`; MATLAB was not run by Codex.

```text
EXACT_SOURCE_RECOVERY=BLOCKED
VALIDATED_EQUIVALENT_RECOVERY=INCOMPLETE
PRODUCTION_PIPELINE_FROZEN=NO
RAIN_G24_PREFLIGHT=NOT_RUN
RAIN_SAGE_EXECUTION=NOT_STARTED
```

Rain remains paused. The next and only gate is normal-user MATLAB syntax/recovery validation; do not run Rain/G24 or production before it passes.

## Final validated-equivalent production recovery freeze (Validated + Frozen; 2026-08-18)

The final normal-user comparison-only run completed successfully using the
preserved G28 actual output:

```text
COMPARISON_NAMESPACE=dataset_generation_logs/darkroom_channel_emulation/production_recovery_compare_existing_20260817T170347Z
PRODUCTION_REFACTOR_REGRESSION=PASS
MATLAB_EXIT_CODE=0
RAW_IQ_OPENED=false
SAGE_EXECUTED=false
```

The final receipt, expanded comparison summary, and schema comparison are
retained in that namespace. All eight Stage1--Stage4 CSVs passed row/schema/
type/exact/categorical/numeric/overall checks with zero numeric error. The
explicit Stage4 identity gate passed for `joint_valid`,
`joint_multipath_count`, path identity including `is_multipath`, and the
confirmed event/path counts. The preceding real full execution evidence
remains Stage0 complete, Stage1 complete, Stage2 54/54, Stage3 complete, and
Stage4 complete.

The frozen production entry is:

```text
scripts/sage_pipeline/run_nav_sage_pipeline.m
VALIDATED_EQUIVALENT_SHA256=bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c
HISTORICAL_ORIGINAL_SHA256=5ff00366f2d71eff7945418ce484b0fedb7199f1144c2db2fb18268fe5b4b0ab
EXACT_SOURCE_RECOVERY=BLOCKED
VALIDATED_EQUIVALENT_RECOVERY=PASS
PRODUCTION_PIPELINE_FROZEN=YES
```

The freeze record is
`dataset_generation_logs/darkroom_channel_emulation/PRODUCTION_SAGE_PIPELINE_FREEZE.md`.
Production is the validated-equivalent monolithic entry and no longer depends
on the shared-core route. `SHARED_CORE_ROUTE=FROZEN_FOR_RAIN_MVP` remains in
force. The Rain branch and darkroom channel-model work must not modify the
production entry or freeze record; every future Rain source task must verify
the frozen production SHA before and after.

```text
RAIN_MATLAB_SYNTAX_SMOKE=PASS
RAIN_G24_PREFLIGHT=NOT_RUN
RAIN_SAGE_EXECUTION=NOT_STARTED
```

No Rain, G24 preflight, production SAGE, raw-IQ, or 20.46 MHz task was run in
this closure. Any next Rain action remains Commander-controlled.
