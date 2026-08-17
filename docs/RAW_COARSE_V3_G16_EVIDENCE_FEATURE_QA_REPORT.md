# Raw-Coarse v3.0 G16 Evidence and Feature QA Report

**QA scope:** `F1023_V70_D0120_P7 / G16 / tracking channel 1 / 10.23 MHz`  
**Decision:** `READY_FOR_POSTERIOR_GOLD_REPLAY=false`  
**Raw capture rerun:** no  
**Stage3/Stage4, confirmed-center and old replay reads:** no  
**Gold labels used for selection:** false

## 1. Scope and protection rules

This report covers the formal v3 subblock evidence artifact and the frozen v3.0 feature/selector output. The audit read only the formal evidence receipt/run manifest, task manifest, Stage0 catalog, and the new v3 feature namespace. It did not read raw IQ, Stage3, Stage4, old coverage replay, confirmed-event locations, or any gold label.

No existing capture receipt or evidence CSV was rewritten. No `scenes/**/sage_results` file was written. The first interrupted artifact, the formal G16 capture namespace, the v2 NumPy kernel and its parameter manifest remain separate and unchanged.

## 2. Formal evidence artifact

Formal evidence namespace:

`dataset_generation_logs/sampling_validation/batch_sampled_v1_3_g16_evidence_outputs_20260812_r1_F1023_V70_D0120_P7_G16_ch1/`

| Item | Result |
|---|---:|
| Stage0 windows | 2,229 |
| Evidence rows | 22,290 |
| B1 `B1_20msx2_D100` | 4,458 = 2,229 × 2 |
| B2 `B2_10msx4_D100` | 8,916 = 2,229 × 4 |
| B2 `B2_10msx4_D200` | 8,916 = 2,229 × 4 |
| Chunk count | 28 |
| Raw bytes recorded by receipt | 1,847,132,692 |
| `stage3_stage4_read` | false |
| `sage_called` | false |
| `gold_labels_used_for_selection` | false |

Evidence QA status: **PASS**.

The QA found exact window/profile/subblock coverage for window IDs 1–2229, no duplicate keys, no missing keys, and no unexpected keys. All rows had the expected task identity, channel, sample-rate and Stage0 sample/NAV mapping. The fixed time mapping was verified as:

- B1 subblock 0 → B2 subblocks 0 and 1;
- B1 subblock 1 → B2 subblocks 2 and 3;
- B1/B2 subblocks 0/1 use `nav_symbol_1`, and subblocks 2/3 use `nav_symbol_2`.

All 22,290 rows were `search_status=valid`, `secondary_status=admissible_delay`, `continuity_status=ok`, and had no `feature_missing_reason`. No raw-short, invalid-RMS, continuity-gap or inconclusive row was present in this formal artifact. Numerical, delay-grid, Doppler-relative identity, null-semantics and deterministic tie-break checks all passed. The D100/D200 diagnostic found 8,916 paired subblocks; 1,768 pairs had all compared core fields textually equal. This is a diagnostic only and is not interpreted as a multipath label.

Evidence QA report:

`dataset_generation_logs/sampling_validation/batch_sampled_v1_3_g16_evidence_qa_20260812_r1_F1023_V70_D0120_P7_G16_ch1/evidence_qa_report.md`

Evidence hashes:

| Artifact | SHA-256 |
|---|---|
| `subblock_evidence.csv` | `60b3259cdc054d3e6b982bf8c03cb620594cfa7db62f7ff57cfa5d1a27d7caa4` |
| `capture_receipt.json` | `00786357bc65be75cfa09ae07b2cbea2673608177171c8280db5ae6c6d7621c1` |
| `capture_run_manifest.json` | `2332facc2512cd109b5bea827c3865d7c59939bd292503742c18a666f4ae0c3b` |
| `evidence_qa_report.json` | `c67c4309b551239337183236b75ea21e399f68316bad302ac287ffe1a9af2f14` |
| `evidence_qa_report.md` | `d5fb19cc88c181239e285deb76fcc8aaa4ef5f5386e221e89f81693a3127115d` |
| task manifest | `b6da2147e0007f83c7ff8c76dcd8306d459ff62f76eccac566f020af053c10ea` |

## 3. Frozen v3.0 feature build

The frozen builder was run only after evidence QA passed, using the existing parameter manifest and without adding temporal persistence, local novelty or robust-z features. The production feature families were:

1. multi-subblock consensus;
2. secondary delay consistency;
3. secondary Doppler consistency;
4. B1/B2 cross-scale agreement.

Feature output namespace:

`dataset_generation_logs/sampling_validation/batch_sampled_v1_3_g16_feature_outputs_20260812_r1_F1023_V70_D0120_P7_G16_ch1/`

The builder produced 2,229 window rows and 188 components. Its run manifest records `stage3_stage4_read=false`, `gold_labels_used_for_selection=false`, and all reserved temporal/novelty features disabled.

| Feature artifact | SHA-256 |
|---|---|
| `v3_window_features.csv` | `330a31efb3bdd3ae94b58497ab80cecc6ed190fb69deda2f471a729be85b95c6` |
| `promotion_manifest.csv` | `e4952df180eb07d56c091ace3bf31b9f08301c265a83b9634e3e3f675a382dc9` |
| `promotion_components.csv` | `2aea6ce8593a047ead04392ee68d7c048e0750e588b4645c1672b196cd8cd099` |
| `feature_run_manifest.json` | `6f740cdbe6c0751c0b1ef682031d3054b03b820f96e9ffd06e167c9e3870c266` |

The parameter manifest hash used by the builder is:

`3f6330f8c88b4901feda2e0cb9bd9e8dcd6350aec6270fd0d3985f5ca2669642`

## 4. Gold-blind selector behavior

The corrected, second-pass selector QA namespace is:

`dataset_generation_logs/sampling_validation/batch_sampled_v1_3_g16_feature_qa_20260812_r1b_F1023_V70_D0120_P7_G16_ch1/`

The first QA pass reported an additional false numeric issue because categorical empty fields were sent through a numeric audit. The QA code was corrected to classify `evidence_status` and `feature_missing_reason` as categorical, and the selector was rerun in a new namespace. The corrected result still fails for the independent component-overlap issue below.

| Selector quantity | Value |
|---|---:|
| Feature/promotion rows | 2,229 / 2,229 |
| Coarse seed windows | 378 (16.9583%) |
| Fixed boundary-expanded windows | 844 (37.8645%) |
| Not promoted / evidence-only rows | 1,007 (45.1772%) |
| Inconclusive rows | 0 |
| Components | 188 |
| Expanded fine-window union | 1,222 (54.8228%) |
| Projected Stage1 reduction | 1,007 windows (45.1772%) |
| Smallest component | 3 windows / 0.06 s |
| Component size p50 / p90 / max | 6 / 10 / 18 windows |
| Component duration p50 / p90 / max | 0.12 / 0.20 / 0.36 s |
| Full-scene component | false |
| Stage2 run | false |

The selector therefore did not saturate to all 2,229 windows. A projected 1,222-window fine set is a workload estimate only; no Stage1 or Stage2 work was run from it.

## 5. Selector QA failure and root cause

Corrected selector QA status: **FAIL**.

The failure is `component_overlap` for 26 window IDs. Examples include windows 89, 139, 410, 417, 495, 775, 779, 785, 930, 944, 991, 1010, 1056, 1230, 1299, 1331, 1676, 1686, 1698, 1919, 1949, 1993, 2091, 2108, 2151 and 2196. Each is listed in two component `component_window_ids` sets.

The precise cause is in the already-frozen v3.0 component semantics: seed windows are grouped when their gap is at most the fixed bridge value 2, but each resulting component is then independently expanded by ±2 windows. Two separate components can therefore have seed separation large enough not to bridge while their boundary expansions still overlap. For example, one component may end at seed 87 and the next begin at seed 91; the two independent expansions both include window 89. The feature table has a single `promotion_component_id` field, so the later assignment overwrites the earlier owner for an overlap. Consequently, the component CSV and feature-row ownership are not a one-to-one partition.

This is a frozen-output semantic inconsistency, not evidence of gold leakage and not a reason to call the overlapping windows multipath. The expanded union count of 1,222 remains a set count, but component-level size, duration, ownership and any downstream component database load are not unambiguous while overlaps remain.

No threshold, tolerance, Doppler grid, feature rule, bridge rule or closure rule was changed to obtain this result. No posterior event position was used to select or explain a window.

Selector QA report and hashes:

| Artifact | SHA-256 |
|---|---|
| `feature_selector_qa_report.json` | `5ffa82c99421feda6b596341c4d3a37d85c8024ea70ad03e601d5556dc0f7908` |
| `feature_selector_qa_report.md` | `c0f83088a0dc46b9439b22eb4f2a2ec1a1e9a335deca6233f62e99686c26434d` |
| `artifact_hashes.json` | `5487feecb7c30e47ff6c055267feea27fd3a6e77f1b8c260a135d0f28333c0d0` |
| feature QA script | `d0cc7b37d6b89909ac8b7f41e4cc7e0ef1d98df1d46eba6ffb0810ccf506921d` |

## 6. Tests and code provenance

`py_compile` passed for both new audit scripts. The relevant regression suites passed:

- `test_raw_coarse_v3.py`: 21 tests passed;
- `test_generate_raw_coarse_v3_g16_task_manifest.py`: 4 tests passed;
- `test_run_batch_sampling_raw_coarse_v1_2_v2.py`: 10 tests passed.

The frozen v3 parameter manifest is:

`dataset_generation_logs/sampling_validation/batch_sampled_v1_3_parameter_manifest_r6_20260812/v3_parameter_schema_manifest.json`

Its SHA-256 is `a83677564cbcf896c2bd2613a918b3efda7e7fdeeeb607e944822db356125d36`.

The source hashes recorded by the feature run were:

- v2 kernel: `959141371075c7f417f945dbe3f915f362a9337bb77582306f2b3ef16919ddfb`;
- `raw_coarse_v3_common.py`: `8cc025ecb8ce06d654ce8c235ba582550cf69509bece5a69a991b49370cab393`;
- `build_raw_coarse_v3_features.py`: `7702a88d0f8c8c7cd88893ba0263c99f62a741d5b1436f1601ba7d13cd04693c`;
- formal evidence-capture source: `9fc8168f9db44511ae40c981bd61a7cb6ae4d55493dc631718d5955f46869cb2`.

## 7. Release decision

| Gate | Result |
|---|---|
| Evidence completeness and identity | PASS |
| Numerical/null/tie-break sanity | PASS |
| Frozen provenance and gold-blind execution | PASS |
| Feature build completion | PASS |
| Selector non-saturation | PASS |
| Selector component ownership/partition QA | FAIL |
| Ready for posterior gold replay | **NO** |

The formal evidence and feature artifacts are retained as immutable diagnostic outputs. They must not be interpreted as confirmed multipath events, and no posterior gold replay is authorized from this namespace.

## 8. Required next step

Stay at the offline prototype layer. In a new versioned namespace, define and test an explicit non-overlapping component ownership/union rule (or an equivalent boundary allocation rule), regenerate only the feature/component QA artifacts, and rerun the same gold-blind selector QA. Do not read Stage3/Stage4 or run posterior gold replay until selector QA is PASS. Do not run G25, G11, sampled SAGE, Wave-2A full-scan or any 20.46 MHz task as part of this result.
