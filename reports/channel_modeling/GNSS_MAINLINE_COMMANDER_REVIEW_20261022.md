# GNSS Mainline Commander Review — 2026-10-22

## A. Git baseline and release scope

- Repository: public `han-yu-xiang/GNSS`, remote URL `https://github.com/han-yu-xiang/GNSS.git`.
- Review branch: `review/gnss-mainline-cir-model-20261022`, based directly on `origin/main` `03f169b0e9a52bb1c271b98155dbfab72f7d418b` to avoid inheriting unrelated local ancestry (including `Berlin.nmea`).
- Task 2 checkpoint commit: `5666349d3a44534d1918abe21e54d059bff786eb`. At this report's preparation, it was local and not yet pushed; the review branch did not yet exist on the remote. No force push or main update is planned.
- The report/handoff update is being prepared as the next explicit commit. The eight pre-existing CIR/ledger MATLAB files copied into this isolated worktree for planned review remain untracked pending Task 3/6; no unrelated root-checkout changes were copied wholesale.

## B. Current SAGE state and Gate A

Fresh reads of the authoritative Summary show `ALREADY_COMPLETE=1, COMPLETE=82, PENDING=4, FAILED=2, IN_PROGRESS=0`, 83/89 complete/accounted. The Manifest's `execution_status` field remains the initial `NOT_STARTED` plan field; live task status is taken from Summary. Current raw-byte hashes:

- Manifest: `52edba87ee8c6726ea905a3f79879c5351131f9f78fd9120c0881e9473731ac5`
- Summary: `9e0d3845b463e98cae96f23a05b6d12eb72a0e42ad3bc71e06a72dd9a9e4cffc`

Gate A's final audit is PASS for 83/83 eligible identities, with zero audit errors. It records 13 scenes / 23 PRNs; Stage0 285,752 valid windows; Stage2 16,761 selected paths = 7,847 direct + 8,914 MPC; Stage3 persistent MPC 2,228; Stage4 strict confirmed MPC 120. Nine scene+PRN elevation summaries remain missing and are not imputed. Evidence is in `reports/data_consolidation_20261003/mainline_1023_model_v1/audit_20261022T074307Z/`.

## C. Task 2 — frozen CIR/model cohort

Gate B PASS. The immutable local artifact is `E:\GNSS_Multipath_Project\dataset_generation_logs\channel_modeling\mainline_1023_cohort_v1_20261022T082520Z\`:

- `cohort.json` SHA-256 `287e891fae0cd294a85c073080611a19b7389ece46240b89cb1d5dab4df90229`
- `cir_tasks.json` SHA-256 `2acbf20f64e961d9391550e3fcef3f3ee66d602f01c456e30c0a47a3c4c10d41`
- Validation: PASS; 83 unique eligible tasks, six excluded, one existing validated G28/ch1 pilot, 82 `NEW_REQUIRED`. Gate A identity set and SHA pins match the current authorities.
- The six excluded records are status-only; no cause is asserted: `run_20261003_F1023_V120_D0121_P2_G06_ch6` (PENDING), `run_20261003_F1023_V120_D0121_P2_G12_ch5` (PENDING), `run_20261003_F1023_V70_D0120_P9_G23_ch10` (PENDING), `run_20261003_F1023_V80_D0117_P8_G29_ch9` (PENDING), `run_20261003_F1023_V70_D0120_P1_G26_ch3` (FAILED), `run_20261003_F1023_V70_D0120_P1_G27_ch8` (FAILED).

The repository snapshot `reports/channel_modeling/mainline_1023_cohort_v1_20261022/` mirrors only the small JSON metadata/index artifacts for public review; it contains no raw IQ or MAT/HDF5 payload.

## D. CIR state

Only the historic pilot `run_20261003_F1023_V70_D0117_P2_G28_ch1` is validated; no new CIR pilot or batch export was executed. Its baseline audit records HDF5 size 253,946,914 bytes, dimensions 35,920 snapshots × 451 delay bins, 898 Stage0 windows × 40 snapshots, and exact PDP read-back (`MAX_PDP_DIFF=0`). This report references the prior audit; this check did not reopen HDF5. The delay grid is −5 to +40 samples in 0.1-sample increments. Receiver gain/AGC is `UNKNOWN`; amplitude is not absolute received power.

Current E: free-space sample: 439,874,486,272 bytes. Existing Dirty/Warning/Full Repair Needed risk remains accepted but unverified. No matching System disk/USB error events were found in the last 72 hours. No active MATLAB, SAGE coordinator/runner, or CIR process was found; no production was started.

## E. Stage2 all-MPC ledger

No new Mainline ledger exists yet. Gate A's 8,914 MPCs are the planned candidate population, with 7,847 direct paths retained as references. Stage3 persistent and Stage4 confirmed/unmapped remain labels, not inclusion gates. The historical 77-row single-pilot ledger is Stage3-gated and is explicitly not reused for this 83-run population. Path-key joins, per-run counts, alpha/CIR joins, and feature audit are not started.

## F. Modeling state

No new Mainline 83-run model, fit, evaluation, model card, or figure has been produced. Historical Phase-1/r3 results remain separate and are not represented as this cohort's results. Scene/run-blocked evaluation, Urban comparisons, uncertainty, and support limits remain planned.

## G. Current blockers and risks

- Task 3 exporter/validator are still pilot-specific (identity and 898-window assumptions) and need minimal parameterization and targeted tests before any new CIR production.
- E: storage health is not verified; existing accepted warning is unchanged. No new matching storage errors were found in this check.
- No other newly observed failure blocks code-only Task 3. New pilot execution remains behind Task 4's normal-user ValidateOnly/launcher, no-overwrite, and QA gates.

## H. Reviewable files and validation

Task 2 checkpoint commit `5666349d3a44534d1918abe21e54d059bff786eb` includes:

- `scripts/channel_modeling/freeze_mainline_1023_cohort.py` — fail-closed 83+6 identity freeze and Gate A SHA binding.
- `scripts/channel_modeling/tests/test_freeze_mainline_1023_cohort.py` — stale Summary, identity, duplicates, excluded substitutions, and output collision tests.
- `reports/channel_modeling/mainline_1023_cohort_v1_20261022/` — frozen cohort, derived CIR tasks, and validation metadata.
- `reports/data_consolidation_20261003/mainline_1023_model_v1/audit_20261022T071844Z/` — Gate A auditor and targeted tests.
- `reports/data_consolidation_20261003/mainline_1023_model_v1/audit_20261022T074307Z/` — final per-task audit, eligible/excluded lists, and machine report.
- `docs/superpowers/plans/2026-10-22-mainline-1023-audit-cir-stage2-model.md` — Gate B progress recorded.

Fresh checks: cohort unit tests 7/7 PASS; real read-only `--validate-only` PASS; exact identity partition 83+6=89, one pilot and 82 new tasks. Staged scope totaled 448,313 bytes across 14 text/JSON/CSV/code files; credential-pattern scan and `git diff --cached --check` were clean. No raw IQ content/hash, MAT/HDF5 payload, MATLAB, SAGE, or CIR execution occurred during Task 2 verification.

**Next task:** Task 3 — write/run the failing multi-identity/window-count tests first, then minimally parameterize exporter and validator. Task 4 pilots and Task 5 batch remain not started. Paper Handoff remains unchanged pending validated CIR/model results.
