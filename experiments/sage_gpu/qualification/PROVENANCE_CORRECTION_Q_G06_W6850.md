# Provenance correction: Q_G06_W6850

```ini
QUALIFICATION_ID=Q_G06_W6850
OLD_VALUE=163.771145454545
NEW_VALUE=163.771145552297
DIFFERENCE_S=0.000000097752
DIFFERENCE_SAMPLES=1.00000296
FORMAL_SAMPLE_START_ZERO_BASED=1675378819
SAMPLE_RATE_HZ=10230000
FORMAL_TIME_RULE=sample_start_zero_based / fs
MANIFEST_TIME_SOURCE_MATCH=previous_sample_index (sample_start_zero_based - 1) / fs, rounded to 12 decimal places
ROOT_CAUSE=MANIFEST_TIME_POINTS_TO_THE_PRECEDING_SAMPLE_INDEX; the exact authoring/transcription mechanism is not recorded.
NUMERICAL_GPU_RESULTS_CHANGED=NO
RAW_IQ_READ_DURING_CORRECTION=NO
```

The formal Stage0, Stage1, Stage2 selected-window, all four Stage2 model-order, and Stage2 selected-path rows agree on `recording_time_s=163.771145552297`. Frozen source `run_nav_sage_pipeline.m` records `recording_time_s = sample_start_zero_based / cfg.fsHz` (line 471); the verified source SHA-256 is `bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c`.

The two other G06/ch9 qualification windows checked, W17197 and W17194, have manifest timestamps matching their formal Stage outputs. The inspected archived `nav_sage_v2` scene tree contains no G06 output. No manifest-generation script or separate selection receipt for this row was found. The correction changes only this row's `recording_time_s`; no other manifest field or numerical GPU result was changed.
