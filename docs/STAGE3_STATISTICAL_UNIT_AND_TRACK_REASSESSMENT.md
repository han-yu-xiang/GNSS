# Stage3 Observation-to-Track Statistical Unit Reassessment

状态：**Completed / independent QA PASS / recommendation issued; no model fit**。

本审计只处理 Stage3 academic-eligible persistent multipath observation 的统计单位设计。它读取已完成的 Stage3 academic reassessment namespace 和冻结 source semantics；不运行 MATLAB/SAGE，不读取 raw IQ，不处理 20.46 MHz，不修改既有 Stage0–Stage4、数据库或模型产物，也不切换现有主分析人口。

## Frozen input and scope

- Prior input path table: `E:\GNSS_Multipath_Project\dataset_generation_logs\channel_modeling\stage3_academic_modeling_reassessment_20260829_r1\stage3_path_population.csv`; prior manifest: `E:\GNSS_Multipath_Project\dataset_generation_logs\channel_modeling\stage3_academic_modeling_reassessment_20260829_r1\audit_manifest.json`.
- Academic input: **783 path observations / 445 centers / 50 runs / 12 scenes / 18 PRNs**.
- This preserves the full 783-row academic-eligible Stage3 population. No row was deleted for track construction; singleton tracks are retained.
- Existing Stage3 source snapshot unchanged: **YES**; prior reassessment namespace unchanged: **YES**.
- Frozen pipeline/wrapper/executor/manifest/inventory hashes match: **YES**.

## Existing association semantics audit

The frozen MATLAB implementation uses `persistenceRadius=2`, `persistenceMinimumConsecutive=3`, delay tolerance 1.5 samples, Doppler tolerance 40 Hz, and power tolerance 10 dB. For each center-local path position it records `matched_window_count`, `longest_consecutive_count`, and a five-position `match_pattern`; a reliable center requires every selected path to pass the persistence rule.

`multipath_id` is `pathIndex-1` after the source path ordering at that center. It is therefore a center-local path position, not an externally verified persistent reflector ID. Stage4 path linkage is likewise positional lineage (`stage4 path_id = multipath_id + 1`) and is used below only as validation.

**CAN_EXISTING_STAGE3_ASSOCIATION_BE_REUSED_FOR_TRACK_BUILDING = PARTIAL.** Reciprocal same-position matches in the existing `match_pattern` can define a reproducible algorithm-level link without introducing a new delay/Doppler/power threshold. They do not establish physical reflector identity or a globally stable path label.

## Observation-to-track graph

Candidate pairs are restricted to the same `run_id×PRN` and the existing ±4-window persistence-footprint overlap range. The graph stores four classes:

- `DEFINITE_ALGORITHM_LINK`: both observations contain each other’s center window in their recorded support and have the same center-local `multipath_id`; only these edges are allowed to merge.
- `POSSIBLE_OVERLAP`: existing persistence support footprints overlap, but there is no reciprocal direct same-position link.
- `AMBIGUOUS`: one-way direct evidence or a path-position mismatch makes identity/order unresolved.
- `NO_LINK`: no shared existing persistence support evidence for the candidate pair.

Edge counts: `{"AMBIGUOUS": 895, "DEFINITE_ALGORITHM_LINK": 605, "NO_LINK": 12, "POSSIBLE_OVERLAP": 60}`. The conservative graph gives **366 algorithm-level tracks**, with median **2** and maximum **5** Stage3 observations per track. This is not a claim of 366 physical reflectors.

The complete graph and node-level degrees are in `observation_to_track_edges.csv` and `observation_to_track_nodes.csv`; the merge rule is intentionally independent of sample size, Stage4 yield, trend separation, or any model-fitting result.

## Elevation audit

- Tracks with non-constant continuous elevation: **0**; tracks crossing a frozen LOW/MID/HIGH boundary: **0**.
- Each track retains continuous elevation minimum/median/maximum/range and its raw bin set. The policy comparison explicitly reports `track_median`, `track_union`, and `track_split_at_bin_boundary`; no first-center or scene-mean elevation was silently substituted.
- If no track crosses a boundary, the three treatments have the same cell support presence; if a track crosses, the report keeps the alternative assignments visible rather than selecting one post hoc.

## Policy comparison

### Policy A — observation level

Every one of the 783 Stage3 path observations is retained as a statistical unit. Uncertainty should be clustered or bootstrapped at scene/run blocks; repeated observations are not treated as independent physical reflectors.

### Policy B — conservative algorithm-derived track

The 366 connected components from reciprocal existing links are the units; singleton observations remain units. Track-level parameter summaries use within-track medians. `track_union` and `track_split_at_bin_boundary` are sensitivity views for elevation assignment, not hidden post-selection.

### Policy C — weighted observation

All 783 observations remain rows, with weight `1/(algorithm-track size)`. Each conservative algorithm track has total weight one, so overlapping center observations do not dominate; uncertainty should still respect run/scene clustering. The CSV reports raw unit count, total weight, and Kish effective count separately.

### Does Env×elevation support depend on observation handling?

Comparing observation-level support with the conservative `track_median` support, the number of cell-presence changes is **0/12**. The empty `Highway/Open–LOW` cell remains empty under every policy/treatment. Track aggregation changes the unit counts and can change parameter medians; the maximum absolute cell-median sensitivity relative to Policy A is recorded without imposing a post hoc materiality threshold: `{"doppler_offset_hz": {"cell_count_compared": 11, "max_absolute_median_difference": "94.399460919"}, "excess_delay_samples": {"cell_count_compared": 11, "max_absolute_median_difference": "0.3"}, "relative_power_db": {"cell_count_compared": 11, "max_absolute_median_difference": "2.605473849"}}`.

Because no final model or inferential threshold is being fitted here, these are descriptive sensitivity results. The primary evidence should carry the observation/clustered view, with the algorithm-track and weighted views reported as dependence sensitivity rather than silently replacing the 783-row population.

## Stage4 validation overlay

Stage4 strict confirmation is not required to create a Stage3 track and was not used for graph edges. Per track, `contains_stage4_confirmed_observation` and `stage4_confirmed_fraction` are retained; **72** tracks contain at least one Stage4 strict-confirmed Stage3-linked observation. See `stage3_stage4_track_validation.csv`.

## Recommendation

```text
CAN_EXISTING_STAGE3_ASSOCIATION_BE_REUSED_FOR_TRACK_BUILDING = PARTIAL
STAGE3_PRIMARY_POPULATION = CONDITIONAL
RECOMMENDED_STATISTICAL_UNIT = WEIGHTED_OBSERVATION
FORMAL_TRACK_RECONSTRUCTION_SUPPORTED = PARTIAL
STAGE3_EFFECTIVE_SAMPLE_SUPPORT = ADEQUATE_WITH_LIMITATIONS
PROCESS_20_46_MHZ_NEXT = CONDITIONAL
NEW_DATA_COLLECTION_REQUIRED = CONDITIONAL
```

Reasoning: the 783-row Stage3 population is broad enough for a bounded descriptive channel-parameter layer and covers 11/12 environment×elevation cells, but it has only 12 scenes and 50 runs in the academic subset, an empty Highway/Open–LOW cell, and center-local rather than globally verified path identity. Reciprocal Stage3 links support a conservative algorithm-track sensitivity layer, not a formal physical-track reconstruction. Therefore the recommended primary treatment retains every observation, normalizes within the reproducible algorithm-link clusters, and uses scene/run-clustered uncertainty. The Stage3 population remains conditional for any stronger fitted model claim.

`PROCESS_20_46_MHZ_NEXT = CONDITIONAL` means do not start that processing merely because this audit is complete; first approve the statistical-unit contract and its limitations. `NEW_DATA_COLLECTION_REQUIRED = CONDITIONAL` means no new collection is required for the bounded 11-cell descriptive layer, but additional independent observations are needed before claiming complete environment×elevation coverage or robust Highway/Open–LOW behavior.

## Independent QA and artifacts

- QA status: **PASS**; QA result: `E:\GNSS_Multipath_Project\dataset_generation_logs\channel_modeling\stage3_statistical_unit_track_reassessment_20260829_r1\qa_result.json`; QA report: `E:\GNSS_Multipath_Project\dataset_generation_logs\channel_modeling\stage3_statistical_unit_track_reassessment_20260829_r1\qa_report.md`.
- New output namespace: `E:\GNSS_Multipath_Project\dataset_generation_logs\channel_modeling\stage3_statistical_unit_track_reassessment_20260829_r1`; report: `E:\GNSS_Multipath_Project\docs\STAGE3_STATISTICAL_UNIT_AND_TRACK_REASSESSMENT.md`.
- New tables: `observation_to_track_nodes.csv`, `observation_to_track_edges.csv`, `track_population.csv`, `policy_unit_summary.csv`, `policy_support_matrix.csv`, `policy_parameter_summary.csv`, `stage3_stage4_track_validation.csv`, and `elevation_policy_comparison.csv`.
- Prior Stage3 reassessment was read from `E:\GNSS_Multipath_Project\docs\STAGE3_ACADEMIC_MODELING_REASSESSMENT.md` and was not overwritten.
- Handoff impact: no existing Engineering/Paper handoff, Stage0–Stage4 source artifact, database, or model artifact was modified. This is a new statistical-unit audit namespace only.

```text
STAGE3_STATISTICAL_UNIT_AUDIT=PASS
STAGE3_ACADEMIC_PATH_OBSERVATIONS=783
STAGE3_ALGORITHM_TRACK_UNITS=366
STAGE3_EDGE_CLASSES={"AMBIGUOUS": 895, "DEFINITE_ALGORITHM_LINK": 605, "NO_LINK": 12, "POSSIBLE_OVERLAP": 60}
STAGE3_TRACK_BIN_CROSSING_COUNT=0
STAGE3_ENV_ELEV_SUPPORT_PRESENCE_CHANGES_A_VS_B_MEDIAN=0
STAGE3_EXISTING_ASSOCIATION_REUSE_FOR_TRACK_BUILDING=PARTIAL
STAGE3_FORMAL_TRACK_RECONSTRUCTION=PARTIAL
STAGE3_PRIMARY_POPULATION=CONDITIONAL
STAGE3_RECOMMENDED_STATISTICAL_UNIT=WEIGHTED_OBSERVATION
RAW_IQ_READ=NO
MATLAB_EXECUTED=NO
SAGE_EXECUTED=NO
FINAL_MODEL_FITTED=NO
NEXT_DECISION_REQUIRED=APPROVE_OR_REVISE_STATISTICAL_UNIT_CONTRACT_BEFORE_ANY_MODEL_FIT
```

This task stops after the statistical-unit recommendation. No final model fit or 20.46 MHz processing was initiated.
