# 10.23 MHz Unattended Mainline Batch Independent QA Report

- QA scope: frozen unattended batch run `20260819T004818Z`
- QA time: 2026-08-25 (Asia/Shanghai)
- Runner state: `completed_pending_batch_qa`
- Request/receipt cardinality: `57/57`
- FINAL QA VERDICT: **PASS**
- QA_RESULT: **57/57 task-level ACCEPTED; 0 REJECTED**
- Raw IQ opened during QA: **no**
- MATLAB/SAGE/batch executed during QA: **no**
- Existing SAGE artifacts, manifest, requests, metadata and inventory modified during QA: **no**

## Evidence and gates

All 57 tasks passed the independent checks for:

- immutable request identity, request SHA, frozen source/executor/wrapper/manifest/inventory hashes;
- `new_only=true`, `resume_allowed=false`, `max_parallel_matlab=1`, 10.23 MHz and normal-user execution contract;
- receipt, execution log, task log, exit code and explicit `Resume=false`;
- 21/21 expected non-empty output files and run-context identity;
- Stage0/Stage1 window identity and scan linkage;
- Stage2 model-order accounting and selected-path linkage;
- Stage3 persistence/reliable-center linkage;
- Stage4 summary/path linkage and finite path fields;
- strict confirmation criterion:
  `joint_valid=1 AND joint_multipath_count>0 AND corresponding stage4_joint_paths.is_multipath=1`.

The three request batch labels are frozen-manifest values, not QA failures:

- `A_pipeline_validation_batch`: 40 tasks — QA accepted as **VALIDATED**, not formal production acceptance;
- `B_main_production_batch`: 14 tasks — QA accepted as formal production tasks;
- `C_long_running_batch`: 3 tasks — QA accepted as formal production tasks.

## Aggregate result

| Quantity | Count |
|---|---:|
| Stage0 40 ms windows | 162864 |
| Stage1 scanned windows | 162864 |
| Stage2 selected windows | 5639 |
| Stage3 reliable centers | 420 |
| Stage4 joint rows | 284 |
| Stage4 joint_valid rows | 284 |
| Strict confirmed events | 88 |
| Strict confirmed paths | 93 |
| Tasks with zero strict confirmed events | 26 |

A zero-event task is a valid result under the current Stage4 criterion and is not a physical-LOS conclusion. No channel parameter, geometry-complete event table, event/path database, or statistical model was created.

## Frozen hashes

```text
pipeline       bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c
python_executor bab7a0422975cb05bcda9a80a75c3577eb7f408a83f2720af2f1e13372b08f1b
wrapper        dd8afb1b3317bf920fe34474e3ceedf06ac4580b2a13c21ea25f8365071143f3
manifest       77c20c0ed6c84fa0348db429948a8bd4900b2e8d86a6d8843b159b9a7a35cf00
inventory      af368feba90797584d7690d4927ed32de604651a5a62662f4adce348a89e4bb4
```

## Task-level ledger

| Seq | Batch | Production task | Stage0 windows | Stage2 selected | Stage3 reliable | Stage4 rows | joint_valid | Strict events | Strict paths |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|
| 001 | C_long_running_batch | F1023_V120_D0121_P2__G25 | 26214 | 70 | 0 | 0 | 0 | 0 | 0 |
| 002 | C_long_running_batch | F1023_V120_D0121_P2__G28 | 26198 | 76 | 0 | 0 | 0 | 0 | 0 |
| 003 | C_long_running_batch | F1023_V120_D0121_P2__G32 | 26198 | 65 | 0 | 0 | 0 | 0 | 0 |
| 004 | B_main_production_batch | F1023_v50_D0127_P1__G11 | 958 | 66 | 0 | 0 | 0 | 0 | 0 |
| 005 | B_main_production_batch | F1023_v50_D0127_P1__G28 | 2151 | 54 | 0 | 0 | 0 | 0 | 0 |
| 006 | B_main_production_batch | F1023_v50_D0127_P1__G29 | 2444 | 49 | 0 | 0 | 0 | 0 | 0 |
| 007 | B_main_production_batch | F1023_v50_D0127_P1__G31 | 1198 | 111 | 18 | 8 | 8 | 0 | 0 |
| 008 | A_pipeline_validation_batch | F1023_V70_D0117_P4__G25 | 893 | 112 | 4 | 4 | 4 | 2 | 2 |
| 009 | A_pipeline_validation_batch | F1023_V70_D0117_P4__G28 | 893 | 117 | 7 | 7 | 7 | 0 | 0 |
| 010 | A_pipeline_validation_batch | F1023_V70_D0117_P4__G29 | 893 | 105 | 12 | 8 | 8 | 1 | 1 |
| 011 | A_pipeline_validation_batch | F1023_V70_D0117_P4__G31 | 892 | 116 | 1 | 1 | 1 | 0 | 0 |
| 012 | A_pipeline_validation_batch | F1023_V70_D0117_P4__G32 | 893 | 102 | 4 | 4 | 4 | 1 | 1 |
| 013 | A_pipeline_validation_batch | F1023_V70_D0120_P1__G26 | 2609 | 111 | 14 | 8 | 8 | 2 | 2 |
| 014 | A_pipeline_validation_batch | F1023_V70_D0120_P1__G27 | 2609 | 110 | 3 | 3 | 3 | 0 | 0 |
| 015 | A_pipeline_validation_batch | F1023_V70_D0120_P1__G29 | 2609 | 104 | 8 | 8 | 8 | 3 | 3 |
| 016 | A_pipeline_validation_batch | F1023_V70_D0120_P1__G31 | 1109 | 111 | 16 | 8 | 8 | 4 | 4 |
| 017 | A_pipeline_validation_batch | F1023_V70_D0120_P5__G18 | 1209 | 115 | 4 | 4 | 4 | 1 | 1 |
| 018 | A_pipeline_validation_batch | F1023_V70_D0120_P5__G23 | 339 | 89 | 10 | 8 | 8 | 0 | 0 |
| 019 | A_pipeline_validation_batch | F1023_V70_D0120_P5__G26 | 1209 | 109 | 13 | 8 | 8 | 2 | 2 |
| 020 | A_pipeline_validation_batch | F1023_V70_D0120_P5__G27 | 276 | 52 | 0 | 0 | 0 | 0 | 0 |
| 021 | B_main_production_batch | F1023_V70_D0120_P7__G18 | 2229 | 119 | 7 | 7 | 7 | 2 | 2 |
| 022 | B_main_production_batch | F1023_V70_D0120_P7__G26 | 2229 | 113 | 6 | 6 | 6 | 0 | 0 |
| 023 | B_main_production_batch | F1023_V70_D0120_P7__G31 | 2229 | 103 | 14 | 8 | 8 | 5 | 5 |
| 024 | A_pipeline_validation_batch | F1023_V70_D0120_P8__G16 | 735 | 110 | 29 | 8 | 8 | 0 | 0 |
| 025 | A_pipeline_validation_batch | F1023_V70_D0120_P8__G18 | 1035 | 115 | 8 | 8 | 8 | 1 | 1 |
| 026 | A_pipeline_validation_batch | F1023_V70_D0120_P8__G23 | 735 | 113 | 5 | 5 | 5 | 0 | 0 |
| 027 | A_pipeline_validation_batch | F1023_V70_D0120_P8__G26 | 1035 | 109 | 9 | 8 | 8 | 1 | 1 |
| 028 | A_pipeline_validation_batch | F1023_V70_D0120_P9__G16 | 2631 | 115 | 4 | 4 | 4 | 1 | 1 |
| 029 | A_pipeline_validation_batch | F1023_V70_D0120_P9__G18 | 2631 | 116 | 14 | 8 | 8 | 0 | 0 |
| 030 | A_pipeline_validation_batch | F1023_V70_D0120_P9__G26 | 2631 | 113 | 12 | 8 | 8 | 1 | 1 |
| 031 | A_pipeline_validation_batch | F1023_V70_D0120_P9__G27 | 898 | 95 | 24 | 8 | 8 | 8 | 8 |
| 032 | A_pipeline_validation_batch | F1023_V70_D0120_P9__G28 | 1498 | 105 | 1 | 1 | 1 | 0 | 0 |
| 033 | A_pipeline_validation_batch | F1023_V70_D0120_P9__G29 | 2630 | 114 | 9 | 8 | 8 | 1 | 1 |
| 034 | A_pipeline_validation_batch | F1023_V70_D0120_P9__G31 | 1730 | 97 | 18 | 8 | 8 | 3 | 3 |
| 035 | B_main_production_batch | F1023_V70_D0122_P1__G13 | 1327 | 114 | 5 | 5 | 5 | 2 | 2 |
| 036 | B_main_production_batch | F1023_V70_D0122_P1__G14 | 1179 | 71 | 0 | 0 | 0 | 0 | 0 |
| 037 | B_main_production_batch | F1023_V70_D0122_P1__G15 | 1629 | 109 | 6 | 6 | 6 | 4 | 4 |
| 038 | B_main_production_batch | F1023_V70_D0122_P1__G17 | 1629 | 109 | 9 | 8 | 8 | 7 | 9 |
| 039 | B_main_production_batch | F1023_V70_D0122_P1__G19 | 1629 | 117 | 1 | 1 | 1 | 1 | 1 |
| 040 | B_main_production_batch | F1023_V70_D0122_P1__G22 | 1629 | 107 | 11 | 8 | 8 | 2 | 2 |
| 041 | B_main_production_batch | F1023_V70_D0122_P1__G24 | 1630 | 108 | 12 | 8 | 8 | 3 | 3 |
| 042 | A_pipeline_validation_batch | F1023_V70_D0122_P2__G10 | 67 | 50 | 0 | 0 | 0 | 0 | 0 |
| 043 | A_pipeline_validation_batch | F1023_V70_D0122_P2__G12 | 898 | 116 | 18 | 8 | 8 | 7 | 9 |
| 044 | A_pipeline_validation_batch | F1023_V70_D0122_P2__G13 | 639 | 63 | 0 | 0 | 0 | 0 | 0 |
| 045 | A_pipeline_validation_batch | F1023_V70_D0122_P2__G19 | 4591 | 110 | 4 | 4 | 4 | 0 | 0 |
| 046 | A_pipeline_validation_batch | F1023_V70_D0122_P2__G23 | 3391 | 107 | 12 | 8 | 8 | 7 | 7 |
| 047 | A_pipeline_validation_batch | F1023_V70_D0122_P2__G24 | 4894 | 115 | 10 | 8 | 8 | 5 | 6 |
| 048 | A_pipeline_validation_batch | F1023_V80_D0117_P8__G12 | 898 | 104 | 2 | 2 | 2 | 0 | 0 |
| 049 | A_pipeline_validation_batch | F1023_V80_D0117_P8__G28 | 1142 | 111 | 17 | 8 | 8 | 3 | 3 |
| 050 | A_pipeline_validation_batch | F1023_V80_D0117_P8__G29 | 1142 | 116 | 10 | 8 | 8 | 1 | 1 |
| 051 | A_pipeline_validation_batch | F1023_V80_D0117_P8__G31 | 898 | 68 | 0 | 0 | 0 | 0 | 0 |
| 052 | A_pipeline_validation_batch | F1023_V80_D0117_P8__G32 | 1134 | 54 | 0 | 0 | 0 | 0 | 0 |
| 053 | A_pipeline_validation_batch | F1023_v90_D0117_P7__G12 | 988 | 107 | 4 | 4 | 4 | 0 | 0 |
| 054 | A_pipeline_validation_batch | F1023_v90_D0117_P7__G25 | 1590 | 109 | 4 | 4 | 4 | 2 | 2 |
| 055 | A_pipeline_validation_batch | F1023_v90_D0117_P7__G28 | 90 | 73 | 6 | 6 | 6 | 1 | 1 |
| 056 | A_pipeline_validation_batch | F1023_v90_D0117_P7__G29 | 1590 | 110 | 6 | 6 | 6 | 0 | 0 |
| 057 | A_pipeline_validation_batch | F1023_v90_D0117_P7__G32 | 1590 | 110 | 9 | 8 | 8 | 4 | 4 |

## Output namespace ledger

This report covers the exact output namespaces recorded in the frozen requests:

`E:\GNSS_Multipath_Project\scenes\F1023_V120_D0121_P2\sage_results\nav_sage_v2\G25` ; `E:\GNSS_Multipath_Project\scenes\F1023_V120_D0121_P2\sage_results\nav_sage_v2\G28` ; `E:\GNSS_Multipath_Project\scenes\F1023_V120_D0121_P2\sage_results\nav_sage_v2\G32` ; `E:\GNSS_Multipath_Project\scenes\F1023_v50_D0127_P1\sage_results\nav_sage_v2\G11` ; `E:\GNSS_Multipath_Project\scenes\F1023_v50_D0127_P1\sage_results\nav_sage_v2\G28` ; `E:\GNSS_Multipath_Project\scenes\F1023_v50_D0127_P1\sage_results\nav_sage_v2\G29` ; `E:\GNSS_Multipath_Project\scenes\F1023_v50_D0127_P1\sage_results\nav_sage_v2\G31` ; `E:\GNSS_Multipath_Project\scenes\F1023_V70_D0117_P4\sage_results\nav_sage_v2\G25` ; `E:\GNSS_Multipath_Project\scenes\F1023_V70_D0117_P4\sage_results\nav_sage_v2\G28` ; `E:\GNSS_Multipath_Project\scenes\F1023_V70_D0117_P4\sage_results\nav_sage_v2\G29` ; `E:\GNSS_Multipath_Project\scenes\F1023_V70_D0117_P4\sage_results\nav_sage_v2\G31` ; `E:\GNSS_Multipath_Project\scenes\F1023_V70_D0117_P4\sage_results\nav_sage_v2\G32` ; `E:\GNSS_Multipath_Project\scenes\F1023_V70_D0120_P1\sage_results\nav_sage_v2\G26` ; `E:\GNSS_Multipath_Project\scenes\F1023_V70_D0120_P1\sage_results\nav_sage_v2\G27` ; `E:\GNSS_Multipath_Project\scenes\F1023_V70_D0120_P1\sage_results\nav_sage_v2\G29` ; `E:\GNSS_Multipath_Project\scenes\F1023_V70_D0120_P1\sage_results\nav_sage_v2\G31` ; `E:\GNSS_Multipath_Project\scenes\F1023_V70_D0120_P5\sage_results\nav_sage_v2\G18` ; `E:\GNSS_Multipath_Project\scenes\F1023_V70_D0120_P5\sage_results\nav_sage_v2\G23` ; `E:\GNSS_Multipath_Project\scenes\F1023_V70_D0120_P5\sage_results\nav_sage_v2\G26` ; `E:\GNSS_Multipath_Project\scenes\F1023_V70_D0120_P5\sage_results\nav_sage_v2\G27` ; `E:\GNSS_Multipath_Project\scenes\F1023_V70_D0120_P7\sage_results\nav_sage_v2\G18` ; `E:\GNSS_Multipath_Project\scenes\F1023_V70_D0120_P7\sage_results\nav_sage_v2\G26` ; `E:\GNSS_Multipath_Project\scenes\F1023_V70_D0120_P7\sage_results\nav_sage_v2\G31` ; `E:\GNSS_Multipath_Project\scenes\F1023_V70_D0120_P8\sage_results\nav_sage_v2\G16` ; `E:\GNSS_Multipath_Project\scenes\F1023_V70_D0120_P8\sage_results\nav_sage_v2\G18` ; `E:\GNSS_Multipath_Project\scenes\F1023_V70_D0120_P8\sage_results\nav_sage_v2\G23` ; `E:\GNSS_Multipath_Project\scenes\F1023_V70_D0120_P8\sage_results\nav_sage_v2\G26` ; `E:\GNSS_Multipath_Project\scenes\F1023_V70_D0120_P9\sage_results\nav_sage_v2\G16` ; `E:\GNSS_Multipath_Project\scenes\F1023_V70_D0120_P9\sage_results\nav_sage_v2\G18` ; `E:\GNSS_Multipath_Project\scenes\F1023_V70_D0120_P9\sage_results\nav_sage_v2\G26` ; `E:\GNSS_Multipath_Project\scenes\F1023_V70_D0120_P9\sage_results\nav_sage_v2\G27` ; `E:\GNSS_Multipath_Project\scenes\F1023_V70_D0120_P9\sage_results\nav_sage_v2\G28` ; `E:\GNSS_Multipath_Project\scenes\F1023_V70_D0120_P9\sage_results\nav_sage_v2\G29` ; `E:\GNSS_Multipath_Project\scenes\F1023_V70_D0120_P9\sage_results\nav_sage_v2\G31` ; `E:\GNSS_Multipath_Project\scenes\F1023_V70_D0122_P1\sage_results\nav_sage_v2\G13` ; `E:\GNSS_Multipath_Project\scenes\F1023_V70_D0122_P1\sage_results\nav_sage_v2\G14` ; `E:\GNSS_Multipath_Project\scenes\F1023_V70_D0122_P1\sage_results\nav_sage_v2\G15` ; `E:\GNSS_Multipath_Project\scenes\F1023_V70_D0122_P1\sage_results\nav_sage_v2\G17` ; `E:\GNSS_Multipath_Project\scenes\F1023_V70_D0122_P1\sage_results\nav_sage_v2\G19` ; `E:\GNSS_Multipath_Project\scenes\F1023_V70_D0122_P1\sage_results\nav_sage_v2\G22` ; `E:\GNSS_Multipath_Project\scenes\F1023_V70_D0122_P1\sage_results\nav_sage_v2\G24` ; `E:\GNSS_Multipath_Project\scenes\F1023_V70_D0122_P2\sage_results\nav_sage_v2\G10` ; `E:\GNSS_Multipath_Project\scenes\F1023_V70_D0122_P2\sage_results\nav_sage_v2\G12` ; `E:\GNSS_Multipath_Project\scenes\F1023_V70_D0122_P2\sage_results\nav_sage_v2\G13` ; `E:\GNSS_Multipath_Project\scenes\F1023_V70_D0122_P2\sage_results\nav_sage_v2\G19` ; `E:\GNSS_Multipath_Project\scenes\F1023_V70_D0122_P2\sage_results\nav_sage_v2\G23` ; `E:\GNSS_Multipath_Project\scenes\F1023_V70_D0122_P2\sage_results\nav_sage_v2\G24` ; `E:\GNSS_Multipath_Project\scenes\F1023_V80_D0117_P8\sage_results\nav_sage_v2\G12` ; `E:\GNSS_Multipath_Project\scenes\F1023_V80_D0117_P8\sage_results\nav_sage_v2\G28` ; `E:\GNSS_Multipath_Project\scenes\F1023_V80_D0117_P8\sage_results\nav_sage_v2\G29` ; `E:\GNSS_Multipath_Project\scenes\F1023_V80_D0117_P8\sage_results\nav_sage_v2\G31` ; `E:\GNSS_Multipath_Project\scenes\F1023_V80_D0117_P8\sage_results\nav_sage_v2\G32` ; `E:\GNSS_Multipath_Project\scenes\F1023_v90_D0117_P7\sage_results\nav_sage_v2\G12` ; `E:\GNSS_Multipath_Project\scenes\F1023_v90_D0117_P7\sage_results\nav_sage_v2\G25` ; `E:\GNSS_Multipath_Project\scenes\F1023_v90_D0117_P7\sage_results\nav_sage_v2\G28` ; `E:\GNSS_Multipath_Project\scenes\F1023_v90_D0117_P7\sage_results\nav_sage_v2\G29` ; `E:\GNSS_Multipath_Project\scenes\F1023_v90_D0117_P7\sage_results\nav_sage_v2\G32`

## Acceptance-state impact

Before this batch, the reconciled formal accepted production count was 9/67, excluding protected historical A3 G16. This batch adds 17 formal production tasks (B+C), so the current formal accepted production count is **26/67**. The 40 A-batch tasks remain **VALIDATED** and are not included in that formal accepted-production count.

The frozen manifest remains unchanged. The protected historical A3 G16 artifact remains `REJECTED_PROTECTED` and is not promoted by this report.

## Next gate

The next planned step is database-rule freeze and a read-only dry-run validator. It must precede any event/path database write, channel-parameter derivation, geometry-complete modeling, or statistical modeling.
