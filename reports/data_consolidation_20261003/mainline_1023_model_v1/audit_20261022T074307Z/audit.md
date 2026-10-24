# Mainline 10.23 MHz cohort audit

- Audit time (UTC): `2026-10-22T07:43:42.629286+00:00`
- Audit status: **PASS**
- Cohort candidates: `83`; excluded by status: `6`
- Manifest SHA-256: `52edba87ee8c6726ea905a3f79879c5351131f9f78fd9120c0881e9473731ac5`
- Summary SHA-256: `9e0d3845b463e98cae96f23a05b6d12eb72a0e42ad3bc71e06a72dd9a9e4cffc`
- Auditor SHA-256: `a1e0925841844aec393ad138354624b324be2d6a86da3fa53d95559e780bc8f0`; targeted tests: `15/15 PASS` (`f2a3a272d0d5850689a063809ee1ad4cce163e91b6eac23dd9cea7f7b4d1ff15`)
- Tooling location: audit package directory; the pre-existing untracked `scripts/channel_modeling` tree was not modified.
- Batch receipt: `PLAN_SCOPE_COMPLETED`; SHA-256 `a77a601bdebe2dbfac9b782e9ed644221ce3bb9a7d2d13957f114bc76db6a293`
- Raw IQ payload read: **NO**; raw IQ hash recomputed: **NO**; MAT/HDF5 payload opened: **NO**; MATLAB/SAGE run: **NO**.

## Current status totals

| Status | Count |
|---|---:|
| ALREADY_COMPLETE | 1 |
| COMPLETE | 82 |
| PENDING | 4 |
| FAILED | 2 |
| IN_PROGRESS | 0 |

## Audited Stage totals

| Measure | Rows |
|---|---:|
| stage0_valid_nav_symbols | 286037 |
| stage0_valid_40ms_windows | 285752 |
| stage1_scanned_windows | 285752 |
| stage2_evaluated_windows | 7847 |
| stage2_selected_path_count | 16761 |
| direct_path_count | 7847 |
| stage2_mpc_count | 8914 |
| stage3_persistence_row_count | 8914 |
| stage3_persistent_mpc_count | 2228 |
| stage4_joint_result_count | 382 |
| stage4_confirmed_mpc_count | 120 |

## Scene, environment, and elevation coverage

| Scene | Tasks |
|---|---:|
| F1023_V120_D0121_P2 | 13 |
| F1023_V70_D0117_P2 | 7 |
| F1023_V70_D0117_P4 | 7 |
| F1023_V70_D0120_P1 | 3 |
| F1023_V70_D0120_P5 | 5 |
| F1023_V70_D0120_P7 | 4 |
| F1023_V70_D0120_P8 | 4 |
| F1023_V70_D0120_P9 | 9 |
| F1023_V70_D0122_P1 | 8 |
| F1023_V70_D0122_P2 | 7 |
| F1023_V80_D0117_P8 | 5 |
| F1023_v50_D0127_P1 | 5 |
| F1023_v90_D0117_P7 | 6 |

| Environment / elevation group | Tasks |
|---|---:|
| Environment: Highway/Open | 18 |
| Environment: Mountain/Valley | 20 |
| Environment: Special Reflective | 16 |
| Environment: Urban | 29 |
| Elevation: High | 20 |
| Elevation: Low | 21 |
| Elevation: MISSING | 9 |
| Elevation: Mid | 33 |

Elevation joins use scene+PRN satellite summary metadata. They do not provide event-time or path-level geometry.

## Excluded identities

The six identities below are omitted from the candidate list by their existing status. No exclusion reasons are included.

| run_id | status |
|---|---|
| `run_20261003_F1023_V120_D0121_P2_G06_ch6` | PENDING |
| `run_20261003_F1023_V120_D0121_P2_G12_ch5` | PENDING |
| `run_20261003_F1023_V70_D0120_P1_G26_ch3` | FAILED |
| `run_20261003_F1023_V70_D0120_P1_G27_ch8` | FAILED |
| `run_20261003_F1023_V70_D0120_P9_G23_ch10` | PENDING |
| `run_20261003_F1023_V80_D0117_P8_G29_ch9` | PENDING |

## Issues and warnings

### Warnings

- `scene_prn_elevation_join_missing` `run_20261003_F1023_V120_D0121_P2_G03_ch2` (F1023_V120_D0121_P2)
- `scene_prn_elevation_join_missing` `run_20261003_F1023_V120_D0121_P2_G19_ch0` (F1023_V120_D0121_P2)
- `scene_prn_elevation_join_missing` `run_20261003_F1023_V120_D0121_P2_G19_ch1` (F1023_V120_D0121_P2)
- `scene_prn_elevation_join_missing` `run_20261003_F1023_V120_D0121_P2_G19_ch3` (F1023_V120_D0121_P2)
- `scene_prn_elevation_join_missing` `run_20261003_F1023_V70_D0117_P4_G31_ch1` (F1023_V70_D0117_P4)
- `scene_prn_elevation_join_missing` `run_20261003_F1023_V70_D0120_P9_G28_ch11` (F1023_V70_D0120_P9)
- `scene_prn_elevation_join_missing` `run_20261003_F1023_V70_D0122_P2_G10_ch6` (F1023_V70_D0122_P2)
- `scene_prn_elevation_join_missing` `run_20261003_F1023_V70_D0122_P2_G12_ch2` (F1023_V70_D0122_P2)
- `scene_prn_elevation_join_missing` `run_20261003_F1023_V70_D0122_P2_G13_ch5` (F1023_V70_D0122_P2)

## Interpretation

`eligible_runs.csv` is an audited candidate list, not the frozen Task 2 cohort. `cohort_eligible=true` is emitted only when the complete audit has no errors and the task row passes.
A PASS covers manifest/summary identity, Stage CSV row and key checks, Stage count reconciliation, receipt fields, metadata-only raw/input availability, and the scene+PRN elevation join. The SAGE writer emits +Inf sentinels for invalid model orders; those are counted as expected sentinels only when model_valid=0, and nonfinite values in valid models fail. Stage4 confirmation mirrors the Coordinator's Stage3-persistent path-key intersection. This is not a full numerical reanalysis of MAT/HDF5 files or a CIR/model validation.
