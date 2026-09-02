# Stage3 Academic Modeling Population Reassessment

Audit timestamp: `2026-08-29T13:15:04+00:00`  
Audit namespace: `E:\GNSS_Multipath_Project\dataset_generation_logs\channel_modeling\stage3_academic_modeling_reassessment_20260829_r1`  
Independent QA: **PASS**

## Scope and guardrails

This is the first, read-only academic-mainline reassessment. It consumes the 64 QA-passed and complete SAGE namespaces listed in the immutable ingestion partition, their Stage0/Stage3/Stage4 CSV artifacts, the existing geometry/time-alignment layer, scene metadata, and frozen provenance hashes. It does not start MATLAB/SAGE, read raw IQ, rerun any batch, modify Stage4/database/model/QA history, fit a new Stage3 model, or process 20.46 MHz data. The fixed engineering/darkroom branches are not used to define this population.

The academic candidate is defined as:

`Stage3 reliable center` + `Stage3 persistence path` + `persistence_pass=true`.

The term “Stage3 reliable/persistent multipath component” denotes an algorithm-level estimate, not external physical ground truth. Stage4 strict joint-confirmation remains a high-confidence validation subset. The Stage3 population is still an observation-level population; repeated reliable center windows within a run can share the existing ±2-window persistence footprints.

## A–C. Population and Stage4 attrition

| quantity | count |
| --- | ---: |
| QA-passed complete runs audited | 64 |
| Stage3 persistence rows (all candidates) | 7471 |
| Stage3 `persistence_pass=true` rows before reliable-center restriction | 1875 |
| Stage3 reliable centers | 447 |
| Stage3 reliable-center path observations | 785 |
| Academic-eligible centers after legacy/context exclusion | 445 |
| Academic-eligible path observations | 783 |
| Elevation-ready centers | 410 |
| Elevation-ready path observations | 716 |
| Stage4 strict-confirmed centers after academic exclusion | 94 |
| Stage4 paths linked back to Stage3 population | 98 |
| Stage4 strict-confirmed multipath paths in source (all contexts) | 104 |

Stage3 reliable-center restriction removes `1090` path rows that individually passed persistence but belonged to a center where not every candidate path passed. This is intentional for the proposed conservative Stage3 population and must not be described as a physical absence of multipath.

Stage4 has `306` available center rows, `94` strict-confirmed academic-eligible centers, `212` available-but-rejected centers, and `139` reliable centers missing because the Stage4 implementation evaluates at most `8` candidates per run. The Stage4 cap is an algorithmic selection mechanism and is a major source of Stage3→Stage4 attrition.

## D. Selection, duplication, and lineage findings

The Stage3-to-Stage4 center link is exact on `(run_id, center_window_id)`. The path link is explicitly positional: `stage4 path_id = stage3 multipath_id + 1`, consistent with the frozen source path construction and Stage4 ordering. It is a lineage link, not a claim that either layer has externally verified path identity.

- Stage3 path observations linked to a Stage4 multipath output: `100`.
- Stage3 paths linked to strict-confirmed Stage4 paths: `98`.
- Stage4 strict-confirmed source paths not found by that Stage3 positional link: `4`.
- Reliable centers with another reliable center within the existing ±2-window persistence radius: `357` of `447`. This is a diagnostic overlap indicator only; no new track/event threshold was introduced.
- Formal track/event consolidation: **not established in this phase**. The tables retain center-window and path-observation granularities and expose overlap indicators so a later Commander-approved deduplication rule can be tested without silently changing the population.

The parameter comparison table tests, descriptively, delay, Doppler, power, matched-window count, consecutive-run count, selected order, and center-level persistence/elevation variables across the full Stage3 population and the Stage4 outcome groups. It does not assign causal meaning to Stage4 selection. The most important confounders are the Stage4 maximum-center cap, Stage4 joint model selection, and repeated center windows.

| group | parameter | n | median | q25 | q75 |
| --- | --- | --- | --- | --- | --- |
| all_stage3_academic_eligible | excess_delay_samples | 783 | 1.9 | 1.4 | 2.6 |
| all_stage3_academic_eligible | doppler_offset_hz | 783 | 28.965544517 | -50.335697905 | 49.664302095 |
| all_stage3_academic_eligible | relative_power_db | 783 | -9.453690722 | -13.178635161 | -3.440209089 |
| stage4_confirmed_link | excess_delay_samples | 98 | 1.5 | 1.3 | 1.9 |
| stage4_confirmed_link | doppler_offset_hz | 98 | 33.802051042 | -43.91923224 | 51.976852935 |
| stage4_confirmed_link | relative_power_db | 98 | -4.973975643 | -11.996875779 | -3.22531013 |
| stage4_available_rejected | excess_delay_samples | 430 | 2 | 1.4 | 2.6 |
| stage4_available_rejected | doppler_offset_hz | 430 | -32.611789443 | -50.335697905 | 49.664302095 |
| stage4_available_rejected | relative_power_db | 430 | -10.284417568 | -13.096805939 | -3.700366552 |
| stage4_cap_missing | excess_delay_samples | 179 | 1.7 | 1.3 | 2.4 |
| stage4_cap_missing | doppler_offset_hz | 179 | 37.908116897 | -47.357784021 | 49.664302095 |
| stage4_cap_missing | relative_power_db | 179 | -5.310551136 | -12.364215276 | -1.881978768 |

## Environment × elevation support

Elevation is kept continuous in the path/center tables and binned only for coverage summaries using the frozen bins `LOW=[0,30)`, `MID=[30,60)`, `HIGH=[60,90]`. Direct Stage3 support exists in **11/12** environment×elevation cells. The no-support cell(s) and sparse cells are shown explicitly; no prior-only values are inserted.

| environment | elevation | eligible_centers | eligible_paths | stage4_confirmed_paths | support |
| --- | --- | --- | --- | --- | --- |
| Urban | LOW | 18 | 18 | 0 | DIRECT_STAGE3_SUPPORT |
| Urban | MID | 117 | 169 | 28 | DIRECT_STAGE3_SUPPORT |
| Urban | HIGH | 63 | 129 | 10 | DIRECT_STAGE3_SUPPORT |
| Special Reflective | LOW | 63 | 81 | 19 | DIRECT_STAGE3_SUPPORT |
| Special Reflective | MID | 8 | 16 | 1 | DIRECT_STAGE3_SUPPORT |
| Special Reflective | HIGH | 31 | 74 | 2 | DIRECT_STAGE3_SUPPORT |
| Mountain/Valley | LOW | 15 | 22 | 5 | DIRECT_STAGE3_SUPPORT |
| Mountain/Valley | MID | 52 | 117 | 9 | DIRECT_STAGE3_SUPPORT |
| Mountain/Valley | HIGH | 14 | 32 | 4 | DIRECT_STAGE3_SUPPORT |
| Highway/Open | LOW | 0 | 0 | 0 | NO_STAGE3_SUPPORT |
| Highway/Open | MID | 19 | 39 | 3 | DIRECT_STAGE3_SUPPORT |
| Highway/Open | HIGH | 10 | 19 | 1 | DIRECT_STAGE3_SUPPORT |

Stage3 materially expands the academic evidence relative to Stage4-only: it provides `445` eligible reliable centers and `783` path observations across `12` scenes and `50` runs, while Stage4 strict confirmation retains `94` eligible centers and `98` linked paths. This supports using Stage4 as a validation subset rather than the sole academic population, subject to the deduplication/weighting conditions below.

## Decisions requested by the audit

- `USE_STAGE3_AS_PRIMARY_ACADEMIC_POPULATION=CONDITIONAL`
  - **Proposed, not applied:** `ACADEMIC_MODELING_POPULATION_V2` would use the academic-eligible Stage3 reliable/persistent population as primary and retain Stage4 strict-confirmed paths as a high-confidence validation subset.
  - Conditions: pre-specify run/scene-block handling and a track/event deduplication or weighting rule; report Stage3 and Stage4 layers separately; do not call Stage3 ground truth; preserve the Stage4 baseline unchanged.
- `PROCESS_20_46_MHZ_NEXT=CONDITIONAL`
  - Do not start it from this audit. First approve the Stage3 population contract and the observation-to-track handling; then a separate 20.46 MHz planning/preflight decision can be made.
- `NEW_DATA_COLLECTION_REQUIRED=CONDITIONAL`
  - Not required to start a bounded Stage3-primary model because Stage3 has direct support in 11/12 cells.
  - Required if the paper claims complete support for every cell or wants stronger independent-scene support for the no-support/sparse cells, especially Highway/Open–LOW and other cells with few independent runs/scenes.

No new `environment_elevation_path_distribution_stage3_v1` fit was performed. It may be proposed after the population contract is approved; the existing Stage4 model remains the immutable high-confidence baseline.

## Frozen provenance check

| hash | expected | actual | match |
| --- | --- | --- | --- |
| pipeline_sha256 | bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c | bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c | True |
| wrapper_sha256 | dd8afb1b3317bf920fe34474e3ceedf06ac4580b2a13c21ea25f8365071143f3 | dd8afb1b3317bf920fe34474e3ceedf06ac4580b2a13c21ea25f8365071143f3 | True |
| executor_sha256 | bab7a0422975cb05bcda9a80a75c3577eb7f408a83f2720af2f1e13372b08f1b | bab7a0422975cb05bcda9a80a75c3577eb7f408a83f2720af2f1e13372b08f1b | True |
| manifest_sha256 | 77c20c0ed6c84fa0348db429948a8bd4900b2e8d86a6d8843b159b9a7a35cf00 | 77c20c0ed6c84fa0348db429948a8bd4900b2e8d86a6d8843b159b9a7a35cf00 | True |
| inventory_sha256 | af368feba90797584d7690d4927ed32de604651a5a62662f4adce348a89e4bb4 | af368feba90797584d7690d4927ed32de604651a5a62662f4adce348a89e4bb4 | True |

The audit source artifact snapshot contains `586` non-raw files and was rehashed after analysis. The independent QA result is `PASS`. Execution gates recorded in the audit are `{"existing_sage_namespace_modified": false, "existing_stage4_modified": false, "matlab_started": false, "raw_iq_read": false, "sage_started": false, "stage3_model_fitting_started": false, "statistical_modeling_started": false}`.

## Deliverables

The CSV tables and independent QA files are in [`E:\GNSS_Multipath_Project\dataset_generation_logs\channel_modeling\stage3_academic_modeling_reassessment_20260829_r1`](E:\GNSS_Multipath_Project\dataset_generation_logs\channel_modeling\stage3_academic_modeling_reassessment_20260829_r1). The report is [`E:\GNSS_Multipath_Project\docs\STAGE3_ACADEMIC_MODELING_REASSESSMENT.md`](E:\GNSS_Multipath_Project\docs\STAGE3_ACADEMIC_MODELING_REASSESSMENT.md). The namespace is new-only and should not be overwritten; subsequent changes require a new versioned namespace.

This task stops here and waits for Commander approval. No automatic population switch, new fitting, batch continuation, MATLAB task, or data collection was initiated.
