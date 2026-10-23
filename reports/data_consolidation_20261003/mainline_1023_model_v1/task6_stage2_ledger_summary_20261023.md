# Task 6 — Stage2 all-MPC ledger audit

**As-of:** 2026-10-23 UTC
**Disposition:** STAGE2_LEDGER_PASS_CIR_ASSOCIATION_PENDING
**Gate F:** not claimed; CIR/PDP feature association and final CIR consistency remain pending Task 5 completion.

## Scope and result

The builder read the frozen Gate A/B cohort of 83 eligible task identities and their Stage2, Stage3, and Stage4 text CSV evidence. It verified the current mainline Manifest and Summary against their frozen SHA pins, verified the cohort bytes against the independently committed Gate B validation digest, and verified all Stage4 joint-summary CSVs against an independently SHA-pinned Task 6 manifest. It then wrote a new-only artifact namespace:

- Full ledger: E:/GNSS_Multipath_Project/dataset_generation_logs/channel_modeling/mainline_1023_model_v1_20261023T135341Z/stage2_ledger.csv
- Machine audit: E:/GNSS_Multipath_Project/dataset_generation_logs/channel_modeling/mainline_1023_model_v1_20261023T135341Z/feature_audit.json
- Lightweight task statistics: E:/GNSS_Multipath_Project/dataset_generation_logs/channel_modeling/mainline_1023_model_v1_20261023T135341Z/stage2_task_summary.csv

The ledger contains **16,761 rows**, exactly matching the Stage2 selected-path total. All 16,761 (run_id, window_id, path_id) keys are unique. The complete population is retained:

| Role | Rows | Treatment |
|---|---:|---|
| Direct/reference paths | 7,847 | Retained in the same ledger as reference rows, not MPC candidates |
| Multipath paths | 8,914 | All retained as the primary modeling candidate population |

Stage3 and Stage4 are annotations only; neither filters the Stage2 candidate population. Stage3 has 8,914 persistence rows, of which 2,228 are persistent. Stage4 confirms 120 MPC identities. The audit also records 1,587 Stage2 MPC rows without a Stage4 confirmation mapping as an explicit unmapped/non-confirmed state, not as a guessed negative. Four Stage4 path rows have no matching Stage2 selected-path key (G06/ch4, window 203, path IDs 3/4; G17/ch2, window 1429, path IDs 3/4). They are reported as Stage4-only identities and do not remove or alter any Stage2 ledger row.

## Descriptive coverage

| Environment | Tasks | Stage2 paths | Direct | MPC candidates | Stage3 persistent | Stage4 confirmed |
|---|---:|---:|---:|---:|---:|---:|
| Highway/Open | 18 | 1,865 | 1,290 | 575 | 147 | 5 |
| Mountain/Valley | 20 | 4,611 | 1,974 | 2,637 | 632 | 27 |
| Special Reflective | 16 | 3,660 | 1,656 | 2,004 | 515 | 43 |
| Urban | 29 | 6,625 | 2,927 | 3,698 | 934 | 45 |
| **Total** | **83** | **16,761** | **7,847** | **8,914** | **2,228** | **120** |

The frozen cohort has categorical elevation groups for 74 tasks: High 20 tasks / 2,797 MPC, Mid 33 / 4,435, and Low 21 / 1,275. The **9 originally missing elevation summaries remain MISSING** and contribute 407 MPC candidates. The cohort has no numeric mean-elevation value for any of the 83 tasks; group labels were not converted into degrees and no elevation value was imputed.

The identity key is exactly (run_id, window_id, path_id). Window rows are repeated/overlapping observations: the ledger records dependence_cluster_id=run_id and window_independence_assumed=NO. No independent-sample assumption or model fit was made. Delay, excess-delay, path-length, Doppler, Doppler-offset, and relative-power fields retain their source units. Relative power is relative dB, not calibrated absolute receive power.

## CIR and modeling boundary

CIR features remain PENDING_TASK5_COMPLETION. No CIR/PDP output was associated, no complex alpha was extracted, and no MAT/HDF5 payload, raw-IQ content, MATLAB, or SAGE computation was used. CIR delay-axis alignment, HDF5 read-back, and final Gate E/F consistency must be validated after Task 5 completes. No model was fit.

At the latest existing Task 5 monitor sample inspected for this audit (2026-10-23 13:35:01.690 UTC), production was RUNNING at run_20261003_F1023_V120_D0121_P2_G06_ch9, with 1/80 completed. The 30-minute monitor task was Ready, had last result 0, and had the next run scheduled for 2026-10-23 22:05 +08. This is a timestamped observation, not a claim about later live state. Task 5 processes, release, coordinator, outputs, and monitor were not started, stopped, edited, or otherwise controlled during Task 6.

## Provenance and verification

Frozen Manifest SHA-256: 52edba87ee8c6726ea905a3f79879c5351131f9f78fd9120c0881e9473731ac5
Frozen Summary SHA-256: 9e0d3845b463e98cae96f23a05b6d12eb72a0e42ad3bc71e06a72dd9a9e4cffc
Cohort SHA-256, externally pinned by the committed Gate B validation: 287e891fae0cd294a85c073080611a19b7389ece46240b89cb1d5dab4df90229
Stage4 summary pin-manifest SHA-256: 32c10789efefe4e87cabee4ac8978cd36a4a132f4d3b5640c8e4b8b0851a635d
Manifest-specific Stage2 ledger SHA-256: bbb8cac8338194b5527e00812a6547129a58466cc5fdd7db36b8c44bba01e551
Machine audit SHA-256: 88b9d1636c0e8b76378bfe2b63d3afb57b4f8c25df5816041190e57f787e2395
83-row task summary SHA-256: 524305c3d108eef3df52a39f09eaf395b37725de0898248648ce781da91a4dbb

Targeted verification: Python compile check passed; 11/11 focused synthetic tests passed after independent review identified and the implementation closed the two source-pin gaps. An independent CSV recount confirmed 16,761 rows, 16,761 unique composite keys, 8,914 MPC, 7,847 direct/reference, and 83 task summaries. The tests cover row conservation, inclusion semantics, identity uniqueness, finite numeric data, stage-label non-gating behavior, missing-elevation preservation, unmapped Stage4 semantics, stale Manifest and cohort pin rejection, Stage4-summary content and pin-manifest digest rejection, and no-overwrite behavior.

The committed lightweight 83-row statistics summary is reports/data_consolidation_20261003/mainline_1023_model_v1/task6_stage2_task_summary_20261023.csv. The independently digest-pinned Stage4 summary inventory is reports/data_consolidation_20261003/mainline_1023_model_v1/stage4_joint_summary_sha256_pins_20261023.json. The full 9.5 MB ledger remains in its new generated artifact namespace and is not duplicated into Git. The Task 6 builder and focused tests are included in the accompanying code change.

**Next:** leave Task 5 uninterrupted. After it completes, perform the planned exact-window CIR/PDP association and HDF5 read-back validation; only after those checks can Gate F and subsequent modeling work be assessed.
