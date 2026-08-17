# G16 Raw-Coarse v3 Posterior Gold Coverage Replay

Overall decision: **FALSE**

This replay was executed only after the frozen selection artifacts passed evidence and ownership gold-blind QA. It did not rebuild features/components or change any scientific selector parameter. Stage3/Stage4 are used here only as posterior gold sources.

## Freeze gate before gold read

- Parent scientific parameter SHA-256: `3f6330f8c88b4901feda2e0cb9bd9e8dcd6350aec6270fd0d3985f5ca2669642`
- Ownership schema SHA-256: `29e557d330fd2b510360ea3bb30a286088032b1a44eb4cb76fe5dc94da4929de`
- Feature SHA-256: `330a31efb3bdd3ae94b58497ab80cecc6ed190fb69deda2f471a729be85b95c6`
- Promotion SHA-256: `e4952df180eb07d56c091ace3bf31b9f08301c265a83b9634e3e3f675a382dc9`
- Membership SHA-256: `2e6038e4b4d230f1aaa308f76b15b1678bbdd3b89481e2fc2442b135b16147c8`
- Evidence QA: `PASS`
- Ownership QA: `PASS`
- Selection artifacts frozen before gold: `True`

## Gold sets

- Confirmed Stage4 centers (4): `[1337, 1338, 1406, 2079]`
- Confirmed center +/-2 unique closure (16): `[1335, 1336, 1337, 1338, 1339, 1340, 1404, 1405, 1406, 1407, 1408, 2077, 2078, 2079, 2080, 2081]`
- Stage3 reliable centers (11): `[947, 957, 959, 965, 966, 1337, 1338, 1393, 1406, 2004, 2079]`
- Stage3 reliable-center +/-2 unique union (44): `[945, 946, 947, 948, 949, 955, 956, 957, 958, 959, 960, 961, 963, 964, 965, 966, 967, 968, 1335, 1336, 1337, 1338, 1339, 1340, 1391, 1392, 1393, 1394, 1395, 1404, 1405, 1406, 1407, 1408, 2002, 2003, 2004, 2005, 2006, 2077, 2078, 2079, 2080, 2081]`

## Coverage summary

| Gold family | Target | Covered | Recall | Direct/core | Guard-only | Uncovered | Inconclusive |
|---|---:|---:|---:|---:|---:|---:|---:|
| confirmed_center | 4 | 2 | 50.0000% | 0 (0.0000%) | 2 (50.0000%) | 2 | 0 |
| confirmed_center_pm2 | 16 | 12 | 75.0000% | 4 (25.0000%) | 8 (50.0000%) | 4 | 0 |
| stage3_reliable_center_pm2 | 44 | 25 | 56.8182% | 8 (18.1818%) | 17 (38.6364%) | 19 | 0 |

`direct/core` means at least one `core_seed` membership. `guard-only` means the unique window is covered only by fixed boundary/closure membership. A not-promoted guard is not relabeled as a selected seed, LOS reference or no-event window.

## Gold-window coverage detail

The complete machine-readable detail is in `posterior_gold_window_coverage.csv`. The following table preserves the promotion state and component membership for every target-family window.

| Family | Window | Promotion | Reason | Coverage | Members | Core | Guard | Inconclusive |
|---|---:|---|---|---|---:|---|---|---|
| confirmed_center | 1337 | not_promoted | secondary_doppler_inconsistent | not_covered | 0 | - | - | false |
| confirmed_center | 1338 | not_promoted | secondary_doppler_inconsistent | not_covered | 0 | - | - | false |
| confirmed_center | 1406 | not_promoted | boundary_expansion_from_coarse_component | guard_only | 1 | - | v3c00122 | false |
| confirmed_center | 2079 | not_promoted | boundary_expansion_from_coarse_component | guard_only | 1 | - | v3c00172 | false |
| confirmed_center_pm2 | 1335 | not_promoted | boundary_expansion_from_coarse_component | guard_only | 1 | - | v3c00115 | false |
| confirmed_center_pm2 | 1336 | not_promoted | boundary_expansion_from_coarse_component | guard_only | 1 | - | v3c00115 | false |
| confirmed_center_pm2 | 1337 | not_promoted | secondary_doppler_inconsistent | not_covered | 0 | - | - | false |
| confirmed_center_pm2 | 1338 | not_promoted | secondary_doppler_inconsistent | not_covered | 0 | - | - | false |
| confirmed_center_pm2 | 1339 | not_promoted | secondary_doppler_inconsistent | not_covered | 0 | - | - | false |
| confirmed_center_pm2 | 1340 | not_promoted | cross_scale_disagreement | not_covered | 0 | - | - | false |
| confirmed_center_pm2 | 1404 | not_promoted | boundary_expansion_from_coarse_component | guard_only | 1 | - | v3c00121 | false |
| confirmed_center_pm2 | 1405 | not_promoted | boundary_expansion_from_coarse_component | guard_only | 1 | - | v3c00122 | false |
| confirmed_center_pm2 | 1406 | not_promoted | boundary_expansion_from_coarse_component | guard_only | 1 | - | v3c00122 | false |
| confirmed_center_pm2 | 1407 | coarse_promoted | multi_subblock_and_cross_scale_consensus | direct_core | 1 | v3c00122 | - | false |
| confirmed_center_pm2 | 1408 | coarse_promoted | multi_subblock_and_cross_scale_consensus | direct_core | 1 | v3c00122 | - | false |
| confirmed_center_pm2 | 2077 | not_promoted | boundary_expansion_from_coarse_component | guard_only | 1 | - | v3c00172 | false |
| confirmed_center_pm2 | 2078 | coarse_promoted | multi_subblock_and_cross_scale_consensus | direct_core | 1 | v3c00172 | - | false |
| confirmed_center_pm2 | 2079 | not_promoted | boundary_expansion_from_coarse_component | guard_only | 1 | - | v3c00172 | false |
| confirmed_center_pm2 | 2080 | coarse_promoted | multi_subblock_and_cross_scale_consensus | direct_core | 1 | v3c00172 | - | false |
| confirmed_center_pm2 | 2081 | not_promoted | boundary_expansion_from_coarse_component | guard_only | 1 | - | v3c00172 | false |
| stage3_reliable_center_pm2 | 945 | not_promoted | boundary_expansion_from_coarse_component | guard_only | 1 | - | v3c00083 | false |
| stage3_reliable_center_pm2 | 946 | coarse_promoted | multi_subblock_and_cross_scale_consensus | direct_core | 1 | v3c00083 | - | false |
| stage3_reliable_center_pm2 | 947 | not_promoted | boundary_expansion_from_coarse_component | guard_only | 1 | - | v3c00083 | false |
| stage3_reliable_center_pm2 | 948 | not_promoted | boundary_expansion_from_coarse_component | guard_only | 1 | - | v3c00083 | false |
| stage3_reliable_center_pm2 | 949 | not_promoted | secondary_doppler_inconsistent | not_covered | 0 | - | - | false |
| stage3_reliable_center_pm2 | 955 | not_promoted | cross_scale_disagreement | not_covered | 0 | - | - | false |
| stage3_reliable_center_pm2 | 956 | not_promoted | secondary_doppler_inconsistent | not_covered | 0 | - | - | false |
| stage3_reliable_center_pm2 | 957 | not_promoted | secondary_doppler_inconsistent | not_covered | 0 | - | - | false |
| stage3_reliable_center_pm2 | 958 | not_promoted | boundary_expansion_from_coarse_component | guard_only | 1 | - | v3c00084 | false |
| stage3_reliable_center_pm2 | 959 | not_promoted | boundary_expansion_from_coarse_component | guard_only | 1 | - | v3c00084 | false |
| stage3_reliable_center_pm2 | 960 | coarse_promoted | multi_subblock_and_cross_scale_consensus | direct_core | 1 | v3c00084 | - | false |
| stage3_reliable_center_pm2 | 961 | not_promoted | boundary_expansion_from_coarse_component | guard_only | 1 | - | v3c00084 | false |
| stage3_reliable_center_pm2 | 963 | not_promoted | secondary_doppler_inconsistent | not_covered | 0 | - | - | false |
| stage3_reliable_center_pm2 | 964 | not_promoted | secondary_doppler_inconsistent | not_covered | 0 | - | - | false |
| stage3_reliable_center_pm2 | 965 | not_promoted | secondary_doppler_inconsistent | not_covered | 0 | - | - | false |
| stage3_reliable_center_pm2 | 966 | not_promoted | secondary_doppler_inconsistent | not_covered | 0 | - | - | false |
| stage3_reliable_center_pm2 | 967 | not_promoted | cross_scale_disagreement | not_covered | 0 | - | - | false |
| stage3_reliable_center_pm2 | 968 | not_promoted | secondary_doppler_inconsistent | not_covered | 0 | - | - | false |
| stage3_reliable_center_pm2 | 1335 | not_promoted | boundary_expansion_from_coarse_component | guard_only | 1 | - | v3c00115 | false |
| stage3_reliable_center_pm2 | 1336 | not_promoted | boundary_expansion_from_coarse_component | guard_only | 1 | - | v3c00115 | false |
| stage3_reliable_center_pm2 | 1337 | not_promoted | secondary_doppler_inconsistent | not_covered | 0 | - | - | false |
| stage3_reliable_center_pm2 | 1338 | not_promoted | secondary_doppler_inconsistent | not_covered | 0 | - | - | false |
| stage3_reliable_center_pm2 | 1339 | not_promoted | secondary_doppler_inconsistent | not_covered | 0 | - | - | false |
| stage3_reliable_center_pm2 | 1340 | not_promoted | cross_scale_disagreement | not_covered | 0 | - | - | false |
| stage3_reliable_center_pm2 | 1391 | not_promoted | boundary_expansion_from_coarse_component | guard_only | 1 | - | v3c00120 | false |
| stage3_reliable_center_pm2 | 1392 | not_promoted | secondary_doppler_inconsistent | not_covered | 0 | - | - | false |
| stage3_reliable_center_pm2 | 1393 | not_promoted | secondary_doppler_inconsistent | not_covered | 0 | - | - | false |
| stage3_reliable_center_pm2 | 1394 | not_promoted | secondary_doppler_inconsistent | not_covered | 0 | - | - | false |
| stage3_reliable_center_pm2 | 1395 | not_promoted | cross_scale_disagreement | not_covered | 0 | - | - | false |
| stage3_reliable_center_pm2 | 1404 | not_promoted | boundary_expansion_from_coarse_component | guard_only | 1 | - | v3c00121 | false |
| stage3_reliable_center_pm2 | 1405 | not_promoted | boundary_expansion_from_coarse_component | guard_only | 1 | - | v3c00122 | false |
| stage3_reliable_center_pm2 | 1406 | not_promoted | boundary_expansion_from_coarse_component | guard_only | 1 | - | v3c00122 | false |
| stage3_reliable_center_pm2 | 1407 | coarse_promoted | multi_subblock_and_cross_scale_consensus | direct_core | 1 | v3c00122 | - | false |
| stage3_reliable_center_pm2 | 1408 | coarse_promoted | multi_subblock_and_cross_scale_consensus | direct_core | 1 | v3c00122 | - | false |
| stage3_reliable_center_pm2 | 2002 | not_promoted | secondary_doppler_inconsistent | not_covered | 0 | - | - | false |
| stage3_reliable_center_pm2 | 2003 | not_promoted | boundary_expansion_from_coarse_component | guard_only | 1 | - | v3c00167 | false |
| stage3_reliable_center_pm2 | 2004 | not_promoted | boundary_expansion_from_coarse_component | guard_only | 1 | - | v3c00167 | false |
| stage3_reliable_center_pm2 | 2005 | coarse_promoted | multi_subblock_and_cross_scale_consensus | direct_core | 1 | v3c00167 | - | false |
| stage3_reliable_center_pm2 | 2006 | coarse_promoted | multi_subblock_and_cross_scale_consensus | direct_core | 1 | v3c00167 | - | false |
| stage3_reliable_center_pm2 | 2077 | not_promoted | boundary_expansion_from_coarse_component | guard_only | 1 | - | v3c00172 | false |
| stage3_reliable_center_pm2 | 2078 | coarse_promoted | multi_subblock_and_cross_scale_consensus | direct_core | 1 | v3c00172 | - | false |
| stage3_reliable_center_pm2 | 2079 | not_promoted | boundary_expansion_from_coarse_component | guard_only | 1 | - | v3c00172 | false |
| stage3_reliable_center_pm2 | 2080 | coarse_promoted | multi_subblock_and_cross_scale_consensus | direct_core | 1 | v3c00172 | - | false |
| stage3_reliable_center_pm2 | 2081 | not_promoted | boundary_expansion_from_coarse_component | guard_only | 1 | - | v3c00172 | false |

## Miss attribution

- window `1337` in `confirmed_center`: `secondary_doppler_consistency`; frozen reason=`secondary_doppler_inconsistent`
- window `1338` in `confirmed_center`: `secondary_doppler_consistency`; frozen reason=`secondary_doppler_inconsistent`
- window `1337` in `confirmed_center_pm2`: `secondary_doppler_consistency`; frozen reason=`secondary_doppler_inconsistent`
- window `1338` in `confirmed_center_pm2`: `secondary_doppler_consistency`; frozen reason=`secondary_doppler_inconsistent`
- window `1339` in `confirmed_center_pm2`: `secondary_doppler_consistency`; frozen reason=`secondary_doppler_inconsistent`
- window `1340` in `confirmed_center_pm2`: `b1_b2_cross_scale_agreement`; frozen reason=`cross_scale_disagreement`
- window `949` in `stage3_reliable_center_pm2`: `secondary_doppler_consistency`; frozen reason=`secondary_doppler_inconsistent`
- window `955` in `stage3_reliable_center_pm2`: `b1_b2_cross_scale_agreement`; frozen reason=`cross_scale_disagreement`
- window `956` in `stage3_reliable_center_pm2`: `secondary_doppler_consistency`; frozen reason=`secondary_doppler_inconsistent`
- window `957` in `stage3_reliable_center_pm2`: `secondary_doppler_consistency`; frozen reason=`secondary_doppler_inconsistent`
- window `963` in `stage3_reliable_center_pm2`: `secondary_doppler_consistency`; frozen reason=`secondary_doppler_inconsistent`
- window `964` in `stage3_reliable_center_pm2`: `secondary_doppler_consistency`; frozen reason=`secondary_doppler_inconsistent`
- window `965` in `stage3_reliable_center_pm2`: `secondary_doppler_consistency`; frozen reason=`secondary_doppler_inconsistent`
- window `966` in `stage3_reliable_center_pm2`: `secondary_doppler_consistency`; frozen reason=`secondary_doppler_inconsistent`
- window `967` in `stage3_reliable_center_pm2`: `b1_b2_cross_scale_agreement`; frozen reason=`cross_scale_disagreement`
- window `968` in `stage3_reliable_center_pm2`: `secondary_doppler_consistency`; frozen reason=`secondary_doppler_inconsistent`
- window `1337` in `stage3_reliable_center_pm2`: `secondary_doppler_consistency`; frozen reason=`secondary_doppler_inconsistent`
- window `1338` in `stage3_reliable_center_pm2`: `secondary_doppler_consistency`; frozen reason=`secondary_doppler_inconsistent`
- window `1339` in `stage3_reliable_center_pm2`: `secondary_doppler_consistency`; frozen reason=`secondary_doppler_inconsistent`
- window `1340` in `stage3_reliable_center_pm2`: `b1_b2_cross_scale_agreement`; frozen reason=`cross_scale_disagreement`
- window `1392` in `stage3_reliable_center_pm2`: `secondary_doppler_consistency`; frozen reason=`secondary_doppler_inconsistent`
- window `1393` in `stage3_reliable_center_pm2`: `secondary_doppler_consistency`; frozen reason=`secondary_doppler_inconsistent`
- window `1394` in `stage3_reliable_center_pm2`: `secondary_doppler_consistency`; frozen reason=`secondary_doppler_inconsistent`
- window `1395` in `stage3_reliable_center_pm2`: `b1_b2_cross_scale_agreement`; frozen reason=`cross_scale_disagreement`
- window `2002` in `stage3_reliable_center_pm2`: `secondary_doppler_consistency`; frozen reason=`secondary_doppler_inconsistent`

## Release decision

`G16_V3_POSTERIOR_COVERAGE_PASS=FALSE`

Frozen projected fine workload: `1222/2229` = `54.8228%`. The workload target was not used to tune or alter the selector.

At least one hard coverage gate failed. Keep v3.0 as an immutable failed experiment and do not prepare G25 from this result; design v3.1 separately without tuning to individual gold windows.

## Gold source hashes

- `stage3_reliable_centers.csv`: `ce5debe12af91ef5241307f780bed8c0094077c483b15438402f8f7b554f6dd2`
- `stage4_joint_summary.csv`: `644ce8f308fa02fc12c9e4fed5538ef8be04135aa40acaa5caab31e671fc6d69`
- `stage4_joint_paths.csv`: `3740157a13eaed27f8c1abd9dd22d1c2bfae61df49ec58e1242b866980123f85`
