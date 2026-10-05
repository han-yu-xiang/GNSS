# GNSS Project Stage Snapshot — 2026-10-05

**STATUS SNAPSHOT ONLY**

**NOT AN AUTHORITY REPLACEMENT**

This is a compact review index. The [Engineering Handoff](../../docs/GNSS_SAGE_ENGINEERING_HANDOFF_CURRENT.md) and [Paper Handoff](../../docs/GNSS_SAGE_PAPER_HANDOFF_CURRENT.md) remain the project authorities. This report branch was created from clean `origin/main` at `03f169b0e9a52bb1c271b98155dbfab72f7d418b`; the dirty business branch was not committed or pushed.

## Frozen SAGE and Mainline batch

```ini
FROZEN_SAGE_AUTHORITATIVE_SHA256=bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c
FROZEN_PRODUCTION_MODIFIED=NO
TOTAL_PLANNED=89
ALREADY_COMPLETE=1
NEW_ATTEMPTED=3
NEW_COMPLETE=3
FAILED=0
PENDING=85
TWO_WORKER_PILOT=PASS
REMAINING_BATCH=PAUSED
```

Counts come from the published [batch summary](../data_consolidation_20261003/MAINLINE_SAGE_1023_BATCH_RERUN_SUMMARY.csv); the 2-worker pilot details are in Engineering Handoff §108. The [rerun manifest](../data_consolidation_20261003/MAINLINE_SAGE_1023_RERUN_MANIFEST.csv) remains unchanged.

Important review-base caveat: `scripts/sage_pipeline/run_nav_sage_pipeline.m` already exists on this clean remote base and was deliberately left unchanged, but its base-file SHA-256 is `9a263f8b45c2402b4232f242893cf407f55f0c362e5cbb7369c3bf310b8589f8`, not the authoritative frozen SHA above. This branch is a read-only review bundle, not an executable frozen-source checkout. The mismatch also explains one existing batch-test failure noted below; the baseline source was not replaced.

## Modeling semantics

```ini
ALL_STAGE2_MULTIPATH=MODELING_POPULATION
STAGE3=PERSISTENCE_ATTRIBUTE
STAGE4=HIGH_CONFIDENCE_ATTRIBUTE
STAGE3_MODELING_GATE=NO
STAGE4_MODELING_GATE=NO
```

Historical Phase-1 Stage3-based analysis remains in its original study scope and is not rewritten.

## GPU experimental status

- Device: RTX 4060 Laptop GPU; MATLAB GPU availability was confirmed in the prior authorized diagnostic.
- `makeReplica` was measured at about 84.81% of CPU profiler self-time; its isolated GPU comparison showed about 5.23× speedup (max absolute difference about `2.98e-13`, relative L2 error about `7.20e-14`).
- Stage2 structural checks passed on the previously tested L1/window 1, L2/window 9, and L3/window 173 examples. For window 173, CPU Stage2 was about 16.26 s, GPU warm Stage2 about 4.42 s, and warm end-to-end speedup about 3.35×. Numeric differences are recorded, not described as exact equality.
- `GPU_PRODUCTION_QUALIFICATION=NOT_COMPLETE`; `GPU_PRODUCTION_ENABLED=NO`. These are Stage2-only diagnostics, not full-task Stage0–Stage4 qualification.
- This review branch generalizes the experimental helper's PRN identity guard. The four-way manifest/formal-task/production-config/helper-request guard tests pass 3/3. The MATLAB helpers require the caller to supply the validated expected PRN; no qualification was invoked in this turn.

See [GPU evidence](GPU_STAGE2_EXPERIMENTAL_EVIDENCE.md) and its [small comparison CSV](GPU_STAGE2_PRELIMINARY_RESULTS.csv).

## GPU qualification status

```ini
PLANNED_WINDOWS=14
EXECUTED_WINDOWS=0
L1=4
L2=5
L3=3
L4=2
SCENES=2
STATUS=PAUSED_BEFORE_EXECUTION
```

The [qualification manifest](../../experiments/sage_gpu/qualification/GPU_STAGE2_QUALIFICATION_MANIFEST.csv) is the plan only; it contains no execution results. No new qualification-window raw IQ was read.

## Known open issues

1. The 14-window GPU qualification has not run.
2. The observed maximum 32.5-sample CIR/SAGE delay-reference difference remains unexplained; it is descriptive, not a threshold or resolved correction.
3. The remaining 85-task CPU batch is paused.
4. GPU has not completed full-task Stage0–Stage4 qualification.

Review checks on this branch: PRN guard tests passed 3/3. The existing single/batch runner suites produced 36 passes and 1 failure; the failure is `recovers only the proven G03 post-run false failure through the coordinator`, where the unchanged remote-base MATLAB file hashes to `9a263f…` but the fixture expects `bffc123…`. This was not repaired by replacing the baseline source.

For this publication turn: `MATLAB_EXECUTED=NO`, `SAGE_EXECUTED=NO`, `NEW_RAW_IQ_READ=NO`, `OTHER_SAGE_TASKS_STARTED=NO`, and `REMAINING_BATCH_RESUMED=NO`.
