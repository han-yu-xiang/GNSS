# RAW-Coarse Phase-A Execution Readiness

Generated: `2026-08-12T02:27:30.020030Z`

## Decision

This document prepares, but does not authorize or execute, the raw-coarse Phase-A run. No raw IQ content was read; MATLAB, SAGE, Stage1, Stage2, Stage3, Stage4, and G11 were not run.

Overall status: `READY_FOR_HUMAN_REVIEW`; execution remains blocked by the explicit human gate and by the current v2 runner's intentional formal-runner refusal.

The only permitted order is:

1. Phase-A1 — `F1023_V70_D0120_P7/G16/ch1/10.23MHz`
2. After an independent G16 QA decision, Phase-A2 — `F1023_v50_D0127_P1/G25/ch0/10.23MHz`

The manifests are immutable by SHA-256 receipt. A changed manifest, code hash, parameter hash, or input receipt invalidates the preparation.

## Frozen implementation

- Parameter SHA-256: `41d3fdedde8a306f14a7de649807857f8d64e7587008b2cf8c4acd1a9c798ed2`
- Kernel: `numpy-batched-complex128-v2-aligned`
- Planner: `batch-sampled-v1.2-b1-b2-c1-prototype-v2-aligned`
- Schema: `batch-sampled-v1.2-raw-coarse-schema-3`
- Python: `D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe`
- NumPy/SciPy/OpenBLAS receipt: `environment_receipt.json` in the readiness namespace
- Frozen profiles: B1 20ms×2 D100 `[-100,0,+100] Hz`; B2 10ms×4 D100 `[-100,0,+100] Hz`; B2 10ms×4 D200 `[-200,0,+200] Hz`.
- `gold_labels_used_for_selection=false`.
- No threshold, Doppler grid, normalization, or promotion rule was changed.

## Task readiness

| Order | Task | Channel | Stage0 rows | Raw bytes | Input checks | Output namespace before run | Status |
|---:|---|---:|---:|---:|---|---|---|
| 1 | `F1023_V70_D0120_P7/G16` | ch1 | 2229 | 3537240576 | `True` | `False` | `READY_FOR_HUMAN_REVIEW` |
| 2 | `F1023_v50_D0127_P1/G25` | ch0 | 2339 | 3882222080 | `True` | `False` | `READY_FOR_HUMAN_REVIEW` |

Both tasks are 10.23 MHz and have unique inventory channel mappings. Their metadata, raw paths, Stage0 catalogs, tracking MAT, telemetry DAT, RINEX NAV, trajectory NMEA, and both satellite geometry CSVs passed the preparation checks.

## Input and hash gates

The manifests record an `input_hash_sha256` built from scene/PRN/channel/sample-rate, metadata SHA-256, Stage0 SHA-256, raw absolute path, raw size, raw mtime, and inventory channel candidates. The full raw content SHA-256 is intentionally not computed during preparation because the raw files are multi-gigabyte; the future executor must repeat path/stat/alignment checks immediately before opening raw IQ.

`pipeline_script_sha256` and `prototype_script_sha256` are frozen separately. They are not expected to be equal: consistency means the manifest receipt matches the exact current files, while the parameter hash matches the passed kernel-alignment receipt. The alignment report states `KERNEL_ALIGNMENT_PASS=true`, `NUMERIC_MICROBENCHMARK_PASS=true`, and `FORMAL_G16_G25_PHASE_A_EXECUTED=false`.

The execution namespace is outside `scenes/*/sage_results`, so it cannot overwrite G06 legacy/reference/full SAGE outputs. Existing `F1023_V70_D0117_P2/sage_results/G06_nav_sage_v1` and reference `nav_sage_v2` outputs were only existence-checked as protected paths; no contents were changed.

## Immutable manifest locations

- Readiness namespace: `E:\GNSS_Multipath_Project\dataset_generation_logs\sampling_validation\batch_sampled_v1_2_phase_a_execution_requests_20260812`
- `Phase-A1` manifest: `E:\GNSS_Multipath_Project\dataset_generation_logs\sampling_validation\batch_sampled_v1_2_phase_a_execution_requests_20260812\phase_a1_g16_20260812\execution_manifest.json`
  - SHA-256: `bca6c592f3d107841f5b2e9459f48cfacb777cfc8cc28c779a91a0be4e70920c`
- `Phase-A2` manifest: `E:\GNSS_Multipath_Project\dataset_generation_logs\sampling_validation\batch_sampled_v1_2_phase_a_execution_requests_20260812\phase_a2_g25_20260812\execution_manifest.json`
  - SHA-256: `d72a5edafc4691333aa9f048386e673c4188acc70c25fdff4608a582ff4fd907`
- Environment receipt: `environment_receipt.json`
- Root receipt: `phase_a_readiness_receipt.json`

## Success gates after human execution

### G16 scientific and engineering gates

- All three frozen profiles must complete without raw read errors or partial status.
- Confirmed-event center recall must be 100% for all four known G16 confirmed centers.
- Each known center's ±2 closure recall must be 100%.
- Stage3 reliable-center closure must be reported.
- Promotion must not degenerate to all Stage0 windows.
- Raw bytes, chunk reuse, wall-clock, CPU time, peak memory, windows/s, and bytes/s must be recorded. The total raw-coarse wall-clock must be materially below the historical G16 full Stage1 background (~3900 s), with the project candidate target at or below 50% of that background.

### G25 control gates

- The complete control run must finish with no raw read error or partial status.
- Report score distributions, promotion fraction, component count, potential fine-window size, and cost.
- Promotion is evidence only; it is not a multipath label, and not-promoted is not LOS.

Only if G16 satisfies center/closure recall, non-all-window promotion, and cost gates, and G25 completes as a control, may the project evaluate whether G11 is eligible. This readiness package does not authorize G11.

## Non-actions and safety rules

- Do not edit `run_nav_sage_pipeline.m`, metadata, inventory, or any scene data.
- Do not overwrite `G06_nav_sage_v1`, reference `nav_sage_v2`, Pilot/ Wave-A SAGE results, or old prototype namespaces.
- Do not read Stage3/Stage4 or known event positions to choose parameters or promote windows. Gold is post-freeze evaluation only.
- Do not tune threshold/Doppler grids, resume, truncate over budget, run G11, restore Wave-2A full-scan, or process 20.46 MHz.
- Do not invoke the current v2 formal CLI as if it were enabled: it intentionally raises `RuntimeError(NumPy backend formal runner is not enabled in this environment)` after its preparation path. A separately reviewed task-aware executor is required before any actual raw read.

## Recommended human action

1. Have `TJ-CHANNEL\Jing_` review the two manifest sidecars and compare all frozen hashes.
2. Resolve the current formal-runner implementation gate through a separately reviewed, task-aware executor that consumes exactly one manifest at a time and preserves the new output namespace.
3. Execute only Phase-A1 G16, perform independent QA, and stop if any gate fails.
4. Only after G16 QA passes, execute Phase-A2 G25 with the same frozen parameter hash and then decide on G11 eligibility.

## Current conclusion

`FORMAL_PHASE_A_EXECUTED=false`. The preparation inputs are complete and the immutable manifests are generated, but `EXECUTION_ALLOWED=false` until human review and the current formal-runner gate are resolved. No G11 execution is allowed.
