# Raw-Coarse v3 Component Ownership/Overlap Schema Fix

**Task:** G16 v3.0 gold-blind component ownership repair  
**Scientific selector retuned:** `false`  
**Raw IQ reread:** `false`  
**Evidence capture rerun:** `false`  
**Stage3/Stage4, coverage replay and gold read:** `false`  
**Final QA:** `PASS`  
**READY_FOR_POSTERIOR_GOLD_REPLAY:** `true`

## 1. What was fixed

The frozen v3.0 selector produced 188 independent evidence components. Their fixed ±2 boundary expansions overlapped at 26 windows. The old single-valued `promotion_component_id` could not represent that relation without overwriting one component owner.

The repair is a schema/ownership revision only. It reads the frozen v3.0 window feature table and component artifact, preserves all scientific selector states, and writes a normalized relation:

`task × window × component → promotion_component_membership.csv`

Boundary overlap is represented as multiple membership rows. Independent core components are not merged merely because their guard expansions touch. The final fine workload is the unique union of task-window keys.

## 2. New versioned namespaces

Schema manifest:

`dataset_generation_logs/sampling_validation/batch_sampled_v1_3_component_ownership_schema_20260812/ownership_schema_manifest.json`

Schema version: `raw-coarse-v3-component-membership-1`  
Schema manifest SHA-256: `1dae14dbdbdd5093aeea479d739a1d8a89e09e9527053030dfd30573f5c18160`  
Ownership schema SHA-256: `29e557d330fd2b510360ea3bb30a286088032b1a44eb4cb76fe5dc94da4929de`

Rebuilt output namespace:

`dataset_generation_logs/sampling_validation/batch_sampled_v1_3_g16_component_ownership_outputs_20260812_r1_F1023_V70_D0120_P7_G16_ch1/`

It contains:

- `promotion_component_membership.csv`;
- normalized `promotion_components.csv`;
- window-level `promotion_manifest.csv` with membership count and deterministic display ID;
- `ownership_run_manifest.json`;
- `ownership_artifact_hashes.json`.

QA namespace:

`dataset_generation_logs/sampling_validation/batch_sampled_v1_3_g16_component_ownership_qa_20260812_r1c_F1023_V70_D0120_P7_G16_ch1/`

## 3. Membership semantics

`membership_type` values are:

- `core_seed`: a parent v3.0 `promotion_status=coarse_promoted` seed belonging to the component's original seed interval;
- `guard`: a fixed parent boundary/closure expansion window that is not a core seed.

`distance_from_core_windows` is the minimum absolute window-ID distance to a core seed in the same component. `boundary_provenance` records whether the row is core evidence or fixed boundary expansion. Each row retains the parent component ID and parent component-artifact SHA-256.

The window-level manifest contains `component_membership_count` and `component_membership_ids`. If `primary_component_id` is present, it is only the lexicographically first component for deterministic display/sorting; it is not scientific ownership.

`not_promoted` semantics are unchanged. A not-promoted window may be present as a guard closure row, but it cannot become a core seed, a multipath label or a LOS label.

## 4. Rebuild and QA results

| Metric | Result |
|---|---:|
| Parent feature windows | 2,229 |
| Coarse seed windows | 378 |
| Guard-promoted rows | 844 |
| Not-promoted rows | 1,851 |
| Inconclusive rows | 0 |
| Preserved core components | 188 |
| Membership rows | 1,248 |
| Unique fine windows | 1,222 |
| Promotion fraction by unique fine windows | 54.8228% |
| Overlap windows | 26 |
| Membership multiplicity 0/1/2 | 1,007 / 1,196 / 26 |
| Maximum membership multiplicity | 2 |
| Core component size min/p50/max | 1 / 2 / 8 |
| Expanded component size min/p50/p90/max | 3 / 6 / 10 / 18 |
| Full-scene component | false |
| Guard-caused component collapse | false |
| Stage2 executed | false |

The unique fine-window count remains exactly `1222/2229`; the schema fix did not change workload, thresholds, tolerances, Doppler grids, component bridge, guard radius or closure radius.

## 5. Provenance

Parent scientific parameter SHA-256:

`3f6330f8c88b4901feda2e0cb9bd9e8dcd6350aec6270fd0d3985f5ca2669642`

This parent SHA is recorded as scientific-selector provenance. It is not reused as the new ownership schema SHA.

Parent frozen artifact hashes:

- feature table: `330a31efb3bdd3ae94b58497ab80cecc6ed190fb69deda2f471a729be85b95c6`;
- parent promotion manifest: `e4952df180eb07d56c091ace3bf31b9f08301c265a83b9634e3e3f675a382dc9`;
- parent component artifact: `2aea6ce8593a047ead04392ee68d7c048e0750e588b4645c1672b196cd8cd099`;
- parent feature run manifest: `6f740cdbe6c0751c0b1ef682031d3054b03b820f96e9ffd06e167c9e3870c266`.

New output hashes:

- `promotion_component_membership.csv`: `2e6038e4b4d230f1aaa308f76b15b1678bbdd3b89481e2fc2442b135b16147c8`;
- normalized `promotion_components.csv`: `14a05d5804c3e45b300655312dcf6a2d89190369dc16845d87e0fbe69e7535ed`;
- window-level `promotion_manifest.csv`: `fd3cdb8f23db00554a3188e79ae3147cf655addd126ae792e5a3a8b6ea9303e9`;
- `ownership_run_manifest.json`: `d7590dcf38ebc608fe4fde5e0f1ddda28baecda5f9b2001f40fe6829dd40a17b`.

Final QA artifacts:

- `ownership_selector_qa_report.json`: `4780ed0196800fe91daf3d8a42832d122ab4db4dcfcb200cf806d25aee30a0dc`;
- `ownership_selector_qa_report.md`: `452f2cc01e3109b21a2c418631b077f1449aeb5af1b3cf224d0512005319622f`;
- `ownership_qa_hashes.json` records the complete release ledger.

## 6. Tests

Python compilation passed. The new ownership regression suite passed 11 tests, covering:

- two-component boundary overlap;
- three-way membership;
- core/guard distinction;
- unique fine union counting;
- no automatic component merge;
- deterministic component IDs and primary display ID;
- preserved `not_promoted` semantics;
- new-only namespace rejection;
- gold/Stage3/Stage4/coverage-replay path rejection;
- separate ownership and parent scientific hashes;
- membership provenance and gold flag.

Existing v3 regression suite also passed 21 tests. No existing v3.0 artifact was modified.

## 7. Release decision

The ownership/schema revision is **PASS** and is `READY_FOR_POSTERIOR_GOLD_REPLAY=true`. This only clears the schema/provenance gate. It does not assert confirmed-event recall or multipath validity. Posterior gold replay remains a separate, explicitly authorized next action and was not performed here.
