# Mainline Stage2 WP3 execution record — 2026-10-28

This file records execution against the approved specification
[`2026-10-28-mainline-stage2-wp3-environment-geometry-modeling.md`](2026-10-28-mainline-stage2-wp3-environment-geometry-modeling.md).
The specification remains unchanged so its run-pinned SHA-256 continues to
identify the exact approved input. This record does not expand that scope.

## Status

`COMPLETED_WITH_LIMITATIONS`; independent scientific review is
`PASS_WITH_LIMITATIONS`. The bounded analysis has not passed Gate G, Gate E/F,
WP6, complete CIR association, or a physical/causal channel-model acceptance.

## Execution and evidence

- Final package:
  `reports/data_consolidation_20261003/mainline_1023_model_v1/wp3_20261028T140100Z/`
- Report:
  `reports/data_consolidation_20261003/mainline_1023_model_v1/wp3_20261028T140100Z/WP3_正式科研报告.md`
  SHA-256 `316c3f6a4abc5bfa34f1593d1512cce424591a45366c9e8e5281ab8fbdf769b5`.
- Runner console:
  `reports/data_consolidation_20261003/mainline_1023_model_v1/wp3_run_20261028T140100Z_console.txt`.
- Analysis completed 2026-10-28 22:01:16–22:04:02 Asia/Shanghai (2m46s),
  exit code 0. Exact command, executable, run times, input hashes and output
  hashes are in `run_manifest.json`; detailed execution output is
  `analysis_execution.txt`.
- Approved plan SHA-256 at execution:
  `4245ca034114ff982df8e835a6be052e8725f9280bf012ca8169da47785714a1`.
- Model module SHA-256:
  `67651a6cea536df1f0d7dcd61b8da034fcc196f903b12250427fc7f1f726ac3b`;
  runner `8e4d7859473c984f4ab652b89c09ca4f4e06c59d8d7ab1a127b3ec2628c6b884`;
  independent validator
  `8452f4c554124011b1e44722db04152f539d855b5c66234e565620d274bff2a1`.
- Focused tests ran under Python 3.12 at 2026-10-28 14:04:50.4007344Z to
  14:04:54.2155934Z. `py_compile` exit 0; `unittest` 18/18 passed, exit 0.
  Full output and exact commands:
  `reports/data_consolidation_20261003/mainline_1023_model_v1/wp3_20261028T140100Z/focused_test_execution.txt`.
- Independent output reconciliation returned `PASS`, zero findings. It
  checked pinned input/output hashes, identity counts, support tables,
  complete-scene fold membership, score and paired-delta recomputation, and
  held-out tail identities. Record:
  `reports/data_consolidation_20261003/mainline_1023_model_v1/wp3_20261028T140100Z/independent_validation_final.json`.
- Separate scientific review:
  `reports/data_consolidation_20261003/mainline_1023_model_v1/wp3_independent_review_20261028/WP3_独立科学审阅与模型选型报告.md`.
  It recommends core M0 working baselines of delay Lognormal, Doppler
  Student-t, and relative-power Student-t (near-tied Normal remains a required
  sensitivity), rejects M1 as a stable predictive gain, and leaves GSV
  relative-power M2 exploratory. A direct read-only check recomputed 810 pair
  differences from 891 scores with 0 identity mismatches, 0 delta mismatches,
  and 0 held-out scenes in training. No new fit or numerical recalculation was
  needed. It also clarifies that `M1-M0` means `score(M1)−score(M0)`.
- Three figures are included in the package `figures/` directory. CSV tables
  include per-scene/source support, descriptive summaries, fold manifest and
  scores, paired scores, ranks, tail diagnostics, parameter stability,
  full-data parameters and supplement applicability scores.

## Population, analysis and bounded findings

- Reconciled 8,914 unique MPC identities, 7,847 unique selected-window
  identities, 83 selected-window runs, 77 MPC-bearing runs and 13 scenes.
  The core population is Urban (6 scenes, 2,927 windows, 3,698 MPC) and
  Mountain/Valley (3 scenes, 1,974 windows, 2,637 MPC). Six runs with selected
  windows but no MPC remain in the window support denominator.
- M0/M1/M2 evaluation uses complete-scene LOSO over the nine core scenes.
  Excess-delay Lognormal ranked first in 9/9 folds. Doppler Student-t ranked
  first in 6/9, Normal in 2/9 and Laplace in 1/9. Relative-power Normal and
  Student-t each ranked first in 4/9, Laplace in 1/9. Rankings are among
  successful candidate fits and are exploratory.
- M1 environment-specific models did not show stable held-out predictive
  improvement over M0. In combined-core scoring, source-pure GSV M2 improved
  relative-power macro score versus M1 across the three families; M2 versus
  M0 and per-environment comparisons were mixed. No universal or causal
  elevation effect is established.
- Tail diagnostics contain 2,268 p05/p50/p95 records, including 279
  unavailable fits and 579 with fewer than ten nominal target-tail path rows.
  These nominal counts are not effective independent sample sizes; no blanket
  tail-calibration PASS is claimed.
- GSV-measured, ephemeris/GGA-height and ephemeris/zero-height observations
  remain separate. Missing elevation is not imputed. Motion remains descriptive
  because 144 source records are reused over 3,372 windows (maximum reuse 96);
  no M3 was fitted. Supplement environments are applicability/descriptive
  checks only.
- Interpretation is conditional on Stage2 selection. The 7,847 windows are
  not all Stage0-valid windows, and unselected windows are not zero-MPC cases.
  Same-scene PRNs, overlapping windows and paths are repeated observations;
  nine scenes (only three Mountain/Valley) and overlapping LOSO training folds
  do not support path-row p-values or ordinary independent-fold confidence
  intervals. Full-data parameter contrasts are descriptive, not held-out
  confirmation.
- Preliminary packages and logs are preserved. The final `140100Z` package
  supersedes earlier optimizer/audit-harness iterations; no historical output
  was deleted or overwritten.

## Execution boundary and next step

No Task 5 process/task/release/audit/receipt/queue/monitor was modified. No
MATLAB, SAGE, CIR, GNSS-SDR, raw-IQ, MAT or HDF5 scientific payload was read;
no alpha export pilot, Gate E/F, Gate G or WP6 was performed.

Next priority: Commander confirms the recommended baseline selection and
exploratory-only relative-power M2 boundary. Do not rerun WP3 or start a real
alpha export pilot without a new scientific question/decision.

### Separate Task 5 sample (read-only, 2026-10-28 22:11:31 +08)

The active release was
`mainline_1023_cir_v1_20261028T120447205Z_task5successor43r1`, request
SHA-256 `1b95146f42a2383f26bbef0bfc1679f9096f3778e67c51fa765af953f04474df`.
Audit was `RUNNING`; four new PASS receipts plus 37 inherited PASS yielded
41/80 cumulative PASS, 4/43 new and 39 new tasks remaining. G18/ch9, G23/ch11,
G26/ch3 and G05/ch10 were the four new PASS identities. G16/ch9 was active:
Coordinator PID 17124, worker PowerShell PID 23592 and MATLAB launcher/worker
PIDs 39444/31756 were present. The batch scheduled task was Running; existing
30-minute monitor last result was 0 (last run 22:05, next 22:35 +08), and the
hourly monitor last result was 0 (last run 22:10, next 23:10 +08). This is a
point-in-time sample only; recheck before operational decisions.

Read-only follow-up at 2026-10-28 22:20:11 +08: the audit remained `RUNNING`
with 5 new PASS (42/80 cumulative; 5/43 new, 38 new tasks remaining). G16/ch9
completed and the current task advanced to
`run_20261003_F1023_V70_D0120_P9_G18_ch1`, started 22:12:48 +08. Coordinator
PID 17124, worker PowerShell PID 29820, MATLAB launcher PID 34664 and MATLAB
worker PID 9748 were present; the MATLAB worker had accumulated 213 CPU
seconds. The Coordinator task was Running; the 30-minute monitor was Ready
(last result 0 at 22:05, next 22:35) and hourly monitor Ready (last result 0 at
22:10, next 23:10). This is an operational sample only, not a batch completion
claim; no Task 5 control or mutation occurred.

Read-only follow-up at 2026-10-28 23:30:40 +08: audit `RUNNING`, 7 new PASS
plus 37 inherited (44/80 cumulative). Current G26/ch6 run started 23:01:45 +08.
Coordinator PID 17124, worker PowerShell PID 20688 and MATLAB
launcher/worker 8812/21660 were present. Batch task Running (LastTaskResult
267009); 30-minute monitor Ready (last result 0 at 23:05, next 23:35), hourly
monitor Ready (last result 0 at 23:10, next 00:10). CPU/file progress and new
System storage events were not sampled; this is not completion or storage
health evidence. No production process or artifact was modified.
