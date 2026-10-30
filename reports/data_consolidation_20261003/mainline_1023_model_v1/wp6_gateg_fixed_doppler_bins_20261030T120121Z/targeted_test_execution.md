# Fixed-bin Gate G targeted test execution record

- Command: `python -m unittest scripts.channel_modeling.tests.test_mainline_stage2_wp6_fixed_doppler scripts.channel_modeling.tests.test_mainline_stage2_wp6_gateg -v`
- Start: `2026-10-30T12:44:45Z`; elapsed: `105.171 s`; exit code: `0`.
- Result: **32/32 PASS**, 0 failures, 0 errors, 0 skipped. This consists of 15 fixed-bin tests and 17 pre-existing Gate G regression tests.
- Full verbose stdout/stderr: `targeted_tests_20261030T124445Z.log` (includes the unittest summary `Ran 32 tests ... OK`).
- Additional syntax check: `python -m py_compile scripts/channel_modeling/mainline_stage2_wp6_fixed_doppler.py scripts/channel_modeling/run_mainline_stage2_wp6_fixed_doppler.py scripts/channel_modeling/validate_mainline_stage2_wp6_fixed_doppler.py scripts/channel_modeling/tests/test_mainline_stage2_wp6_fixed_doppler.py`; exit code `0`.

The fixed-bin tests cover bin edge conventions and invalid widths, discrete marginal mass and grouped fitting, mixed Gaussian rectangle normalization/identity behavior and numerical validation, held-out scene isolation, nested training-only selection, exact M0/C0 paired support, and explicit failed-fit handling. The prior Gate G regression tests protect delay-cell, identity, tie-aware and scene-pairing behavior. No production task, SAGE, CIR, alpha, MATLAB, HDF5, MAT or raw-IQ payload was run or read by these tests.

## Scope boundary

Passing tests establish covered implementation behavior only. They do not establish a generalizable dependence benefit, path exchangeability, count-invariant marks, a complete joint generator, or physical channel truth. Independent numerical recomputation and scene-out scientific interpretation are documented separately in `WP6_GateG_固定箱宽Doppler独立科学审阅.md` and `independent_validation_portable.json`.
