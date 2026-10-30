# Portable execution and provenance record

- Analysis window: `2026-10-30T12:01:21Z` to `2026-10-30T12:43:10Z` (41m49s; Asia/Shanghai 20:01:21–20:43:10 +08).
- Runtime: Windows 11, Python 3.12.9, NumPy 2.5.2, pandas 3.0.5, SciPy 1.18.1.
- Recorded runner: `scripts/channel_modeling/run_mainline_stage2_wp6_fixed_doppler.py`; output package: this directory. The runtime execution record is retained locally for full machine details; this portable record intentionally uses repository-relative input paths.
- Scope: frozen lightweight CSV only; no SAGE, CIR, alpha, MATLAB, MAT/HDF5, raw-IQ, or production computation/read.
- Population: 7,847 Stage2-selected windows, 8,914 MPC, 83 Stage2 run IDs, 13 scenes; fixed-bin mark scores cover the 4,273 MPC-bearing selected windows.
- Score config: 0-Hz-centered half-open Doppler bins, tie-to-upper; 5 Hz primary and fixed 10/20 Hz sensitivities; quadrature order 24; no width selected from data. Outer validation is 13-scene LOSO with nested training-only marginal-family selection and training-only Copula fitting.

## Frozen inputs

| Input | Repository-relative path | Rows | SHA-256 |
|---|---|---:|---|
| Stage2/CIR/PDP window features | `reports/data_consolidation_20261003/mainline_1023_model_v1/wp4_gate_ef_final_20261029T181100/stage2_cir_pdp_window_features.csv` | 7,847 | `258d5d70081d9ee6fd82a64b1a4f9c405180bc18cd49280b0e2b799d9a482bf4` |
| Stage2 MPC / alpha linkage | `reports/data_consolidation_20261003/mainline_1023_model_v1/wp4_gate_ef_final_20261029T181100/stage2_mpc_cir_alpha_linkage.csv` | 8,914 | `8db941db20e684108d13583d67ee20cde543bf2a36ca01013d1288b48231c80b` |

## Executed source identities

| Source | SHA-256 |
|---|---|
| `scripts/channel_modeling/mainline_stage2_wp3.py` | `67651a6cea536df1f0d7dcd61b8da034fcc196f903b12250427fc7f1f726ac3b` |
| `scripts/channel_modeling/mainline_stage2_wp6.py` | `a1fae7384c713067d82e67b60478a4d037e9a5825ff7d471bfdc536b0e37422a` |
| `scripts/channel_modeling/mainline_stage2_wp6_gateg.py` | `431513e4024bdb90f595965026dcc178a5ffcc864d63cc38b50a118584702cfc` |
| `scripts/channel_modeling/mainline_stage2_wp6_fixed_doppler.py` | `de4c9fca1ac77593d87f6c285257a16ff2fa7adbf4b8b02e59e1d0e7782682f6` |
| `scripts/channel_modeling/run_mainline_stage2_wp6_fixed_doppler.py` | `8eb8ef67718dc84a77fa71374cd7e8bb65e504ae03d5f1f256ff2889cf3851ea` |
| `scripts/channel_modeling/validate_mainline_stage2_wp6_fixed_doppler.py` | `77c488ce38f135c0b321fd217e4ca3c58c76b96e77b75d1daa1faca221d3529b` |

Analysis outputs and result-table hashes are enumerated in `independent_validation_portable.json`; the full test log is `targeted_tests_20261030T124445Z.log`. The machine-local `execution_record.json` and `input_code_manifest.json` contain absolute workstation paths and are not included in this portable record.

## Outcome

Analysis process exit code 0; 13/13 outer scenes completed. Independent validation is `PASS_WITH_LIMITATIONS` (116 checks, 0 failures; 9 independent quadrature samples). Targeted tests are 32/32 PASS, and `py_compile` exited 0. This certifies the fixed-bin analysis implementation and recorded support, not a generalizable Copula advantage or complete joint/physical generator.
