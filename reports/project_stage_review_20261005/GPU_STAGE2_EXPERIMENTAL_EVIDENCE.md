# GPU Stage2 Experimental Evidence

**Scope:** previously completed CPU outputs only; Stage2 diagnostic experiments. This is not 14-window qualification, full-task GPU validation, or production qualification. No result MAT, IQ, HDF5, or large profiler artifact is included in this review bundle.

The CPU probe is a one-window experimental entry point. Its source also contains local copied/reinserted helper bodies; it is not the frozen MATLAB source, a production runner, or an authorization to run Stage0–Stage4.

## Previously established evidence

- Reference task: `G03/ch2`; reference window 173, recording time `600.232764516129 s`.
- CPU helper vs frozen production on window 173: `PASS_EXACT` for the recorded Stage2 comparison.
- CPU/GPU `makeReplica`: max absolute difference approximately `2.98e-13`, relative L2 error approximately `7.20e-14`; isolated speedup approximately `5.23x`.
- GPU Stage2 structural checks: L1/window 1, L2/window 9, and L3/window 173 passed on the tested examples. Numeric differences were recorded; no bitwise or exact-numeric claim is made.
- Window 173 L3 retry trace: candidate rank 1 at delay 2 had minimum separation `0.7000000000000002` samples and was rejected; candidate rank 2 at delay 4 had minimum separation `1.2999999999999998` samples and was accepted. This is observed trace evidence, not a window-specific rule.
- Window 173 timing: CPU Stage2 `16.2626666 s`; GPU warm Stage2 `4.4199535 s`; compute-only speedup `3.6794x`; warm end-to-end speedup `3.3522x`; transfer in `0.06947 s`, transfer out `0.0034307 s`.

Detailed per-window timing and numeric deltas are in [GPU_STAGE2_PRELIMINARY_RESULTS.csv](GPU_STAGE2_PRELIMINARY_RESULTS.csv). The evidence was transcribed from small previously-created diagnostic MAT outputs, which are intentionally not published.

## Published experimental source

- [CPU Stage2 reference probe](../../experiments/sage_gpu/stage2_window_173_probe.m)
- [GPU Stage2 helper and GPU `makeReplica`](../../experiments/sage_gpu/stage2_window_173_gpu_probe.m)
- [Separated residual-candidate retry helper](../../experiments/sage_gpu/selectSeparatedResidualCandidate.m) and [its small MATLAB test](../../experiments/sage_gpu/test_selectSeparatedResidualCandidate.m)
- [Four-source PRN identity validator](../../experiments/sage_gpu/qualification/Assert-GpuQualificationPrnIdentity.ps1) and [Pester tests](../../experiments/sage_gpu/qualification/tests/Assert-GpuQualificationPrnIdentity.Tests.ps1)
- [14-window qualification manifest](../../experiments/sage_gpu/qualification/GPU_STAGE2_QUALIFICATION_MANIFEST.csv)

The CPU/GPU probe signatures now take the expected numeric PRN from validated task metadata and compare it to `cfg.targetPrn` before processing the window. The PowerShell guard cross-checks manifest PRN, formal task PRN, production-config PRN, and helper-request PRN. A mismatch fails closed with `INPUT_IDENTITY_VALIDATION=FAIL`. The mathematical search, grids, thresholds, precision, candidate order, BIC, refinement, and retry implementation were not changed in this guard update.

## Limits

`GPU_STAGE2_STRUCTURAL_CHECKS=PASS_ON_TESTED_L1_L2_L3_EXAMPLES` does not imply broad qualification. The 14 planned windows remain unexecuted, GPU production remains disabled, and the frozen CPU pipeline has not been replaced.
