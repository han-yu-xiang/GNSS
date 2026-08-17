# Production SAGE Pipeline Freeze Record

Freeze date: 2026-08-18

## Frozen file

```text
FILE:
scripts/sage_pipeline/run_nav_sage_pipeline.m

HISTORICAL_ORIGINAL_SHA256:
5ff00366f2d71eff7945418ce484b0fedb7199f1144c2db2fb18268fe5b4b0ab

EXACT_SOURCE_RECOVERY:
BLOCKED

VALIDATED_EQUIVALENT_SHA256:
bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c

VALIDATION_BASELINE:
F1023_V70_D0117_P2 / G28 / ch1

REGRESSION:
PASS
```

## Final validation evidence

The final normal-user MATLAB comparison-only namespace was:

```text
dataset_generation_logs/darkroom_channel_emulation/production_recovery_compare_existing_20260817T170347Z/
```

Its receipt records:

```text
status=PASS
comparison_mode=existing_output_read_only
raw_iq_opened=false
sage_executed=false
MATLAB_EXIT_CODE=0
PRODUCTION_REFACTOR_REGRESSION=PASS
comparison_overall_pass=true
baseline_unchanged=true
```

The final comparison recorded equal schema/type/order and zero numeric or
exact mismatches for all eight Stage1--Stage4 CSVs. The explicit Stage4
confirmation identity gate passed for `joint_valid`,
`joint_multipath_count`, path identity including `is_multipath`, and the
confirmed event/path counts. The preserved full execution evidence remains:

```text
Stage0 completed
Stage1 completed
Stage2 54/54 evaluated
Stage3 completed
Stage4 completed
```

The exact historical source bytes were not recovered. This freeze therefore
means validated-equivalent recovery, not `EXACT_SOURCE_RECOVERY=PASS`.

## Freeze policy

- Production pipeline is frozen.
- The Rain branch must not modify this file or
  `scripts/sage_pipeline/run_nav_sage_pipeline.m`.
- Darkroom channel-model work must not modify this file or the production
  entry.
- Shared-core work must not modify this file or the production entry.
- Any future production-entry modification requires explicit Commander
  approval.
- Every Rain source-code task must verify the production SHA before and after
  the task.
- The expected frozen production SHA is
  `bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c`.

## Current branch gates

```text
EXACT_SOURCE_RECOVERY=BLOCKED
VALIDATED_EQUIVALENT_RECOVERY=PASS
PRODUCTION_EXECUTION=PASS
PRODUCTION_REFACTOR_REGRESSION=PASS
PRODUCTION_PIPELINE_FROZEN=YES
SHARED_CORE_ROUTE=FROZEN_FOR_RAIN_MVP
RAIN_MATLAB_SYNTAX_SMOKE=PASS
RAIN_G24_PREFLIGHT=NOT_RUN
RAIN_SAGE_EXECUTION=NOT_STARTED
```

No Rain task, G24 preflight, production SAGE task, raw-IQ processing, or
20.46 MHz task is authorized by this record.
