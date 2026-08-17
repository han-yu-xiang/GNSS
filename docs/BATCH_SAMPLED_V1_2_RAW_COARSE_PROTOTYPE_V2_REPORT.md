# Batch-sampled-v1.2 raw-coarse prototype v2 report

## Verdict

**FAIL**.  This namespace is prototype-only.  MATLAB, SAGE, Stage2, Stage3 and Stage4 were not called by the v2 evaluator.

## Frozen implementation

- Namespace: `E:\GNSS_Multipath_Project\dataset_generation_logs\sampling_validation\batch_sampled_v1_2_prototype_v2_retry`
- Planner: `batch-sampled-v1.2-b1-b2-c1-prototype-v2`
- Kernel: `stdlib-fallback-smoke-only-v1`
- Parameter SHA-256: `214d2cc3fbf1ad32c235eabc0fcf1e27db29b6f1c67c2955aacd6f35a1ab00cf`
- Backend: `unavailable; standard-library smoke fallback only`
- True Doppler offsets: B1/B2-D100 `[-100, 0, 100]` Hz; B2-D200 `[-200, 0, 200]` Hz.
- Gold labels used for selection: `false`.

## Microbenchmark

The fixed G16 subset was selected from Stage0 catalog positions `[0, N//3, 2N//3, N-1]` before any gold file was opened.

- Numeric equivalence: `True`
- Old wall-clock: `0.14139470015652478` s
- New wall-clock: `0.14475489989854395` s
- Speedup: `0.9767869706353686`
- Mismatches: `0`
- Tolerance: score `1e-08`, peak ratio `1e-08` dB, delay `0` samples, Doppler `1e-08` Hz.

Peak-Doppler old-vs-new equivalence is unavailable because the legacy manifest did not retain the selected Doppler; v2 records it explicitly and does not infer a legacy value.

## Phase-A status

- Phase A complete: `False`
- G11 allowed: `False`
- G16/G25 raw passes: `[]`
- Reason: `preflight blocked`

No formal G16/G25 raw pass is executed when the compiled backend preflight fails.  This prevents the known slow fallback from being presented as an optimized result.

## Safety

All v2 output is under the new sampling-validation namespace. Existing pre-fix prototype output, `sage_results`, metadata, inventory, pipeline code, and execution requests are not modified.

## Sole next step

Provide an already-installed compiled numeric backend (for example NumPy/SciPy in the approved Windows user environment), then run a fresh v2 Phase-A with a new parameter hash/namespace. Do not install from the network, tune against gold event windows, run G11, resume Wave-2A full-scan, or process 20.46 MHz.
