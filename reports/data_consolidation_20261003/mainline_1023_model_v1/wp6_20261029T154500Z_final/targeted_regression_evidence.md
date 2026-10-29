# WP6 最终复核执行证据

All times below are UTC; Windows local time was UTC+08:00. Commands were run from the project root in the isolated worktree. Test fixtures are synthetic and temporary; model analysis/validation read the fixed CSV inputs and wrote only to this new result directory.

| Check | Command / scope | Start–end | Result |
| --- | --- | --- | --- |
| Real WP6 rerun | `python scripts/channel_modeling/run_mainline_stage2_wp6.py --output-dir reports/data_consolidation_20261003/mainline_1023_model_v1/wp6_20261029T154500Z_final` | 2026-10-29 15:38:37–15:43:01 | exit 0; `COMPLETE`; 264.404 s; 83 runs / 7,847 windows / 8,914 MPC |
| Focused tests | `python -m unittest discover -s scripts/channel_modeling/tests -p test_mainline_stage2_wp6.py -v` | log created 15:46:55Z, finished 15:47:09Z | exit 0; 39/39 PASS; 14.456 s |
| Full channel-modeling suite | `python -m unittest discover -s scripts/channel_modeling/tests -v` | log created 15:47:17Z, finished 15:48:23Z | exit 0; 222/222 PASS; 65.815 s |
| Compile | `python -m py_compile scripts/channel_modeling/mainline_stage2_wp6.py scripts/channel_modeling/mainline_stage2_wp3.py scripts/channel_modeling/run_mainline_stage2_wp6.py scripts/channel_modeling/validate_mainline_stage2_wp6.py scripts/channel_modeling/tests/test_mainline_stage2_wp6.py` | 2026-10-29 15:48:50Z | exit 0 |
| Independent validation | `python scripts/channel_modeling/validate_mainline_stage2_wp6.py reports/data_consolidation_20261003/mainline_1023_model_v1/wp6_20261029T154500Z_final --features reports/data_consolidation_20261003/mainline_1023_model_v1/wp4_gate_ef_final_20261029T181100/stage2_cir_pdp_window_features.csv --mpcs reports/data_consolidation_20261003/mainline_1023_model_v1/wp4_gate_ef_final_20261029T181100/stage2_mpc_cir_alpha_linkage.csv` | 2026-10-29 15:50:09.367Z–15:50:41.942Z | exit 0; `PASS_WITH_LIMITATIONS`; 7,847 windows / 8,914 MPC; 52/52 PDP score rows |

Raw console artifacts are retained beside this file. The unit-test logs end with the `unittest` aggregate and `EXIT_CODE=0`; the validator log includes UTC start/end and exit code. Python bytecode compilation returned exit 0. Analysis/validation JSON created by the runner contain the originating local worktree path; portable SHA/provenance and validation summaries are recorded separately in `wp6_provenance_git.json` and `independent_validation_git.json`.

Independent reviewer follow-up: no Critical, Important, or Minor findings remained after checking the final code, tests, figures, and report. No production task was started or modified.
