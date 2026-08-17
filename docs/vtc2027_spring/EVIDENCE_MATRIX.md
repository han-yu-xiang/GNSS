# VTC2027-Spring Evidence Matrix

This matrix is a claim-control document for the VTC paper. `Available` means that an existing artifact or independent QA supports the bounded claim; it does not mean that a complete database or final statistical analysis exists.

## 1. Dataset and environment coverage

| Claim/evidence cell | Status | Source | Notes |
|---|---|---|---|
| Overall dataset contains 19 scenes | Available | `docs/GNSS_SAGE_PAPER_HANDOFF_CURRENT.md`; `dataset/dataset_inventory.csv` | Overall project scope |
| 13 scenes at 10.23 MHz and 6 at 20.46 MHz | Available | `dataset/dataset_inventory.csv`; `dataset_generation_logs/production_planning_10mhz_20260812/scene_metadata_10MHz.csv` | VTC production scope is 10.23 MHz only |
| 10.23 MHz metadata covers 13 scenes | Validated | `dataset_generation_logs/production_planning_10mhz_20260812/scene_metadata_10MHz.csv`; `docs/scene_metadata_10MHz_check_report.md` | Scene metadata layer, not full SAGE completion |
| Urban / Mountain-Valley / Highway-Open / Special-Reflective classes | Available | `scene_metadata_10MHz.csv` | Metadata labels; not a prediction of event richness |
| All 13 scenes have final paper-ready path results | Missing | Production QA and summary outputs | Production is ongoing |

## 2. Geometry and elevation evidence

| Claim/evidence cell | Status | Source | Notes |
|---|---|---|---|
| LOW = 0–30°, MID = 30–60°, HIGH = 60–90° | Defined | `docs/GNSS_SAGE_PAPER_HANDOFF_CURRENT.md`; paper methodology/schema | Definition only |
| Elevation/azimuth/SNR diagnostic is available from NMEA/GSV-derived geometry outputs | Available | `scenes/<scene_id>/satellite/`; preprocessing logs; handoff | Must preserve provenance |
| RINEX NAV is used for navigation/PRN support, not broadcast-ephemeris position reconstruction | Validated limitation | `docs/GNSS_SAGE_PAPER_HANDOFF_CURRENT.md` | Do not claim a new ephemeris solver |
| Window-level TOW geometry join is production-validated for all paper samples | Missing/Partial | Geometry diagnostics and handoff | Must be QA-complete before strong elevation claims |

## 3. Pipeline and validation cases

| Case | Status | Evidence source | Permitted paper statement |
|---|---|---|---|
| Reference `F1023_V70_D0117_P2`, seven PRNs | Completed / Validated | `scenes/F1023_V70_D0117_P2/sage_results/reference_scene_final_validation_report.md`; `prn_validation_summary.csv` | Same scene shows control, rejected-candidate, and confirmed cases under the hierarchy |
| Wave-A G16/G25/G12 (distinct from formal A3 G16) | Completed / Validated | `docs/WAVEA_10MHz_VALIDATION_REPORT.md`; individual QA reports | Cross-task execution-chain validation, not population statistics |
| Formal A1 G11 | Completed / QA PASS | `docs/10MHz_FULL_SAGE_PRODUCTION_A1_G11_QA_REPORT.md`; output directory | 3 confirmed events and 3 confirmed paths under the criterion |
| Formal A2 G18 | Completed / QA PASS | `docs/10MHz_FULL_SAGE_PRODUCTION_A2_G18_QA_REPORT.md`; output directory | Valid zero-confirmed-event output; not a physical no-multipath claim |
| Formal A3 G16 | Scientific artifact QA PASS with execution-policy caveat | `docs/10MHz_FULL_SAGE_PRODUCTION_A3_G16_QA_REPORT.md`; output directory | Scientific pipeline validation case; not Batch A release evidence |
| Controlled G12 | Completed / QA PASS / **Available** | `docs/10MHz_FULL_SAGE_PRODUCTION_CONTRACT_ACCEPTANCE_G12_QA_REPORT.md`; `dataset_generation_logs/batch_sage_execution/batch_sage_execution_20260814T024904Z/` | 3 confirmed events and 3 paths under the current Stage4 criterion; available evidence, not yet a core VTC Results claim |

## 4. Path-level evidence

| Claim/evidence cell | Status | Source | Notes |
|---|---|---|---|
| Confirmed event/path criterion is Stage4-based | Validated | Stage4 QA reports and handoff | `joint_valid=1`, `joint_multipath_count>0`, and `is_multipath=1` path row |
| Excess delay examples exist in reference/A1 path outputs | Available | Reference Stage4 path CSVs; A1 output/QA | Exact figure values must be extracted directly |
| Relative Doppler and relative power examples exist | Available/needs aggregation | Reference/A1 Stage4 path outputs | Do not infer values from Stage2 alone |
| Path-count observations | Available for validated tasks | Stage4 summaries/path tables and QA reports | Cross-scene denominator not complete |
| Path lifetime/temporal persistence | Partial | Stage3 persistence and Stage4 artifacts | Use only where extraction is reproducible |
| Complete path database | Missing | `docs/paper_draft/GNSS_MULTIPATH_DATABASE_SCHEMA.md` | Schema designed; tables not built |

## 5. Computational and reproducibility evidence

| Claim/evidence cell | Status | Source | Notes |
|---|---|---|---|
| Full Stage0–Stage4 pipeline exists and has completed validation cases | Validated | `scripts/sage_pipeline/run_nav_sage_pipeline.m`; reference/Wave-A/A1/A2 QA | SAGE is used as extraction tool |
| Normal-user Windows wrapper and immutable request chain | Validated | `scripts/sage_pipeline/Invoke-BatchSageWindows.ps1`; execution receipts and QA | Engineering reproducibility evidence |
| Long-record scalability observation | Available | `docs/WAVE2A_G11_QA_REPORT.md` | 15,210 windows; Stage1 ~8.1 h; Stage2 ~11.4 h; total ~19.6 h |
| Sampling/raw-coarse v3 is a valid production acceleration method | Failed/Frozen | `docs/RAW_COARSE_V3_G16_POSTERIOR_GOLD_COVERAGE_REPORT_R1B.md` | Must be presented as negative/limitation result |

## 6. Claim admission checklist

Before a claim enters the final manuscript, record:

1. the exact source file and namespace;
2. whether the source passed independent QA;
3. whether the claim is a result, a limitation, or a planned analysis;
4. whether the statement distinguishes Stage2/Stage3 evidence from Stage4 confirmation;
5. whether environment/elevation denominators are complete enough for the claimed comparison.

No cell in this matrix authorizes a new experiment or changes an execution gate.

## 8. Special Reflective evidence gap: T1-1 preparation (2026-08-14)

| Evidence cell | Status | Source | Notes |
|---|---|---|---|
| Special Reflective / LOW candidate `F1023_V70_D0120_P9/G05/ch10` | `REQUEST_PREPARED / READY_FOR_HUMAN_EXECUTION` | `dataset_generation_logs/batch_sage_execution_requests/vtc_priority_t1_1_d0120p9_g05_20260814/execution_request.json`; `preflight_report.md`; dry-run report | Request and non-MATLAB dry-run passed; no Stage0-Stage4 result or scientific evidence is available yet |

This row records preparation status only. It must not be counted as a completed scene, confirmed-path case, zero-event case, or available paper result. Independent human execution and QA are still required.

## 9. Special Reflective evidence: T1-1 QA result (2026-08-14)

| Evidence cell | Status | Source | Notes |
|---|---|---|---|
| `F1023_V70_D0120_P9/G05/ch10` full-SAGE production | `Available / QA PASS` | `docs/10MHz_FULL_SAGE_PRODUCTION_T1_1_G05_QA_REPORT.md`; `dataset_generation_logs/batch_sage_execution/batch_sage_execution_20260814T060453Z/`; `scenes/F1023_V70_D0120_P9/sage_results/nav_sage_v2/G05/` | Stage0–Stage4 complete; 2 confirmed events and 2 confirmed paths under the fixed Stage4 criterion |
| Special Reflective environment evidence | `Available` | Same QA report and `scene_metadata_10MHz.csv` | One independently QA-passed production case; not a complete environment database |
| LOW geometry planning context | `Available / scene-level only` | VTC priority queue and geometry summary provenance | Mean elevation approximately 19.327°; not an event-level elevation assignment |

The earlier T1-1 preparation row remains as history, but is superseded for current status by this QA-passed result. At that historical point T1-2 and T1-3 were pending; the current T1-2 preparation state is recorded below, and this matrix does not authorize execution.

## 10. Highway/Open evidence: T1-2 request preparation (2026-08-14)

| Evidence cell | Status | Source | Notes |
|---|---|---|---|
| `F1023_V80_D0117_P8/G25/ch10` Highway/Open HIGH candidate | `REQUEST_PREPARED / READY_FOR_HUMAN_EXECUTION` | `dataset_generation_logs/batch_sage_execution_requests/vtc_priority_t1_2_v80p8_g25_20260814/execution_request.json`; `preflight_report.md`; dry-run report | Current inventory/metadata/provenance and unique channel mapping passed; output is absent; no Stage0–Stage4 result or scientific evidence exists yet |
| Highway/Open environment evidence | `Pending execution and QA` | T1-2 request/preflight only | This preparation does not predict confirmed events, zero events, LOS behavior, or Stage4 rejection |
| HIGH geometry planning context | `Prepared / scene-level only` | T1-2 request and current geometry provenance | Mean elevation approximately 79.0°; not an event-level elevation result |

The preparation-only state above is superseded by the QA result below. T1-3 remains `NOT_PREPARED`; no T1-3 request was created.

## 11. Highway/Open evidence: T1-2 independent QA result (2026-08-14)

| Evidence cell | Status | Source | Notes |
|---|---|---|---|
| `F1023_V80_D0117_P8/G25/ch10` full-SAGE production | `Available / QA PASS` | `docs/10MHz_FULL_SAGE_PRODUCTION_T1_2_G25_QA_REPORT.md`; `dataset_generation_logs/batch_sage_execution/batch_sage_execution_20260814T075945Z/`; `scenes/F1023_V80_D0117_P8/sage_results/nav_sage_v2/G25/` | Stage0–Stage4 complete; 2 confirmed events and 2 confirmed paths under the fixed Stage4 criterion |
| Highway/Open environment evidence | `Available` | Same QA report and `scene_metadata_10MHz.csv` | One independently QA-passed production case; not a complete environment database or statistical conclusion |
| HIGH geometry planning context | `Available / scene-level only` | T1-2 request, run context and geometry provenance | Mean elevation approximately 79.0°; not an event-level elevation assignment |

T1-2 closes the current Highway/Open production evidence gap for one scene. It adds bounded path-level delay, relative Doppler and relative power evidence, but does not establish an elevation effect or a Highway/Open distribution. Mountain/Valley remains the next minimum evidence gap under the current VTC plan and requires a separate Commander decision before any T1-3 request.

## 7. Evidence-priority production strategy (2026-08-14)

Batch A continuous production is released after the repaired G12 controlled acceptance, but VTC submission does not require completion of all 67 manifest tasks. The current planning queue is `docs/vtc2027_spring/VTC_PRODUCTION_PRIORITY_QUEUE.md`.

The queue review found 48 Batch A manifest rows, four existing target namespaces, and 44 new-only candidates after excluding the accepted A1 G11, controlled G12, A2 G18 and protected historical A3 G16 artifact. The first planned wave contains one task each from Special Reflective, Highway/Open and Mountain/Valley. This is a coverage strategy, not a prediction of confirmed events.

The next production decision remains conditional on independent QA after each task. The matrix must be updated before another request is generated. The minimum stop condition is bounded evidence for the four environment classes (or an explicitly narrowed paper claim), usable LOW/MID/HIGH analysis denominators, a confirmed-path case, a Stage4 rejection/control case, a valid zero-event production case, and traceable sources for the planned VTC figures. None of these planning statements marks an unexecuted task as completed.

## 12. Mountain/Valley evidence: T1-3 request preparation (2026-08-14)

| Evidence cell | Status | Source | Notes |
|---|---|---|---|
| `F1023_v90_D0117_P7/G11/ch6` Mountain/Valley MID candidate | `REQUEST_PREPARED / READY_FOR_HUMAN_EXECUTION` | `dataset_generation_logs/batch_sage_execution_requests/vtc_priority_t1_3_v90p7_g11_20260814/execution_request.json`; `preflight_report.md`; dry-run report | Current manifest/inventory/metadata/provenance and unique channel mapping passed; output is absent; no Stage0–Stage4 result exists |
| Mountain/Valley environment evidence | `Prepared / pending execution and QA` | T1-3 request and preflight only | No confirmed event, zero-event, LOS, rejection, or statistical conclusion is filled in |
| MID geometry planning context | `Prepared / scene-level only` | T1-3 request and `F1023_v90_D0117_P7_satellite_elevation_summary.csv` | Mean elevation `35.0°`; not an event-level elevation assignment |

At preparation time T1-3 was the only newly prepared request. T1-1 and T1-2 remain `Available / QA PASS`; the preparation did not authorize execution.

## 13. Mountain/Valley evidence: T1-3 independent QA result (2026-08-15)

| Evidence cell | Status | Source | Notes |
|---|---|---|---|
| `F1023_v90_D0117_P7/G11/ch6` full-SAGE production | `Available / QA PASS` | `docs/10MHz_FULL_SAGE_PRODUCTION_T1_3_G11_QA_REPORT.md`; `dataset_generation_logs/batch_sage_execution/batch_sage_execution_20260815T132956Z/`; `scenes/F1023_v90_D0117_P7/sage_results/nav_sage_v2/G11/` | Stage0–Stage4 complete; 1 confirmed event and 1 confirmed path under the fixed Stage4 criterion |
| Mountain/Valley environment evidence | `Available` | Same QA report and `scene_metadata_10MHz.csv` | One independently QA-passed task-level case; not a complete environment database or statistical conclusion |
| MID geometry planning context | `Available / scene-level only` | T1-3 request, run context and geometry provenance | Mean elevation approximately `35.0°`; not an event-level elevation assignment |
| Window-level TOW geometry join | `Missing/Partial` | Current geometry diagnostics and handoff | Still blocks geometry-QA-complete LOW/MID/HIGH denominators |

T1-3 closes the current Mountain/Valley task-level evidence gap, but it does not by itself satisfy the VTC minimum stop condition. The required geometry/time-alignment QA remains outstanding; therefore no T1-4 request is authorized by this update.

## 14. VTC evidence consolidation and geometry QA (2026-08-15)

Commander decision: `STOP SAGE PRODUCTION`. No T1-4/T1-5 request, MATLAB run, SAGE run, or production artifact modification is authorized by this evidence-consolidation step.

| Evidence cell | Status | Source | Notes |
|---|---|---|---|
| Confirmed path evidence index | `Implemented / QA audited` | `docs/vtc2027_spring/evidence/vtc_confirmed_path_database.csv` | 5 rows: T1-1 G05=2, T1-2 G25=2, T1-3 G11=1; every row links to Stage4 path/summary, Stage0 TOW and the independent QA report |
| Zero-confirmed-event case | `Available / QA PASS` | `docs/10MHz_FULL_SAGE_PRODUCTION_A2_G18_QA_REPORT.md`; `scenes/F1023_V70_D0120_P1/sage_results/nav_sage_v2/G18/` | Valid complete output with 0 confirmed events/paths under the fixed Stage4 criterion; not a physical LOS/no-reflection claim |
| Stage4 rejection/non-confirmation evidence | `Available / QA PASS` | T1-1/T1-2/T1-3 QA reports and their Stage4 summaries | 6, 6 and 7 valid joint rows respectively have zero multipath count; these are conservative non-confirmation outcomes |
| Event-level geometry/time alignment | `Partial` | `docs/vtc2027_spring/evidence/vtc_geometry_alignment_qa.md` | 5/5 provisional nearest NMEA/GSV matches; 0/5 geometry-complete joins because the absolute observation-clock bridge and GPS-UTC provenance are not frozen |
| Environment diversity | `Available / bounded task-level` | T1 QA reports, scene metadata and evidence index | Special Reflective, Highway/Open and Mountain/Valley are represented; this is not a complete environment database or statistical result |

The evidence index is a paper traceability layer, not the long-term event database or channel-parameter database. Geometry candidate values remain explicitly provisional and must not be used to create LOW/MID/HIGH event-level denominators. `NEXT_VTC_DECISION_REQUIRED = YES`; owner: Commander.

## 15. Special Reflective supplement G15 (2026-08-17)

| Evidence cell | Status | Source | Notes |
|---|---|---|---|
| `F1023_V70_D0122_P2/G15/ch8` full-SAGE production | `Available / QA PASS` | `docs/vtc2027_spring/evidence/VTC_SPECIAL_REFLECTIVE_SUPPLEMENT_G15_QA_REPORT.md`; execution receipts/logs; `scenes/F1023_V70_D0122_P2/sage_results/nav_sage_v2/G15/` | Stage0–Stage4 complete; 3687 windows, 108 selected, 432 model evaluations, 10 reliable centers, 8 valid joint rows, 5 confirmed events and 5 confirmed paths |
| Special Reflective environment evidence | `Available / replicated but bounded` | `docs/vtc2027_spring/evidence/VTC_ENVIRONMENT_EVIDENCE_CENSUS.csv`; `VTC_ENVIRONMENT_PATH_CANDIDATES.csv`; `vtc_confirmed_path_database.csv` | Two independent scenes and tasks, 7 confirmed events and 7 paths in total; descriptive evidence only, not a statistical distribution |
| Coherence semantic status | `Defined at event/joint-model level only` | `scripts/sage_pipeline/run_nav_sage_pipeline.m`; G15 QA report; `vtc_confirmed_path_database.csv` | `stage4_joint_summary.maximum_coherence` is the maximum normalized cross-correlation between distinct fitted path replicas; `stage4_joint_paths.csv` has no path-level coherence field, and the paper path tables do not treat it as one |
| Event-level geometry/elevation | `Missing / Partial` | Current geometry alignment QA and G15 QA report | No event-level elevation assignment; scene-level Special Reflective context must not be converted into LOW/MID/HIGH event denominators |
| Paper inclusion decision | `KEEP_IN_MAIN_ENVIRONMENT_COMPARISON` | `VTC_SPECIAL_REFLECTIVE_SUPPLEMENT_G15_QA_REPORT.md` | Bounded descriptive comparison only; the current main comparison uses delay, relative Doppler and relative power |

The G15 supplement was independently executed and QA-passed before this section was added. It does not authorize another production task: Commander `STOP SAGE PRODUCTION` remains in force, and `NEXT_VTC_DECISION_REQUIRED = YES` remains the current decision gate.
