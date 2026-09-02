# Fixed Three-NLOS-Slot Activation Model v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and independently validate an auditable environment × elevation activation layer that decides whether a simulation block contains confirmed-support NLOS, samples an active NLOS path count `K in {1,2,3}`, and maps those paths into three fixed slots without changing the frozen path-parameter or main/common-gain models.

**Architecture:** Use a two-part hierarchical hurdle model. Part 1 estimates a conservative `Stage4-confirmed-support occupancy proxy` from unique `confirmed center ±2` window unions over valid Stage0 exposure; Part 2 estimates `P(K=1,2,3 | active)` from the 94 modeling-eligible Stage4-confirmed events. A deterministic slot mapper converts `K` to prefix masks `000/100/110/111`, orders active paths by excess delay, and keeps inactive slots explicit. A separate auditor independently verifies source hashes, Stage4 semantics, exposure/closure accounting, posterior normalization, slot identities, deterministic draws, new-only isolation, and protected-pipeline integrity.

**Tech Stack:** Python 3.12; NumPy 2.5.1; SciPy 1.18.0; OpenBLAS from `D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe`; standard-library CSV/JSON/gzip/hash/dataclass/path utilities; pytest. No dependency installation is permitted.

**Spec:** `docs/GNSS_SAGE_ENGINEERING_HANDOFF_CURRENT.md` Sections 51–54; `docs/ENVIRONMENT_ELEVATION_PATH_DISTRIBUTION_MODEL_V1_REPORT.md`; `docs/MAIN_PATH_COMMON_GAIN_FADE_MODEL_V1_REPORT.md`; `dataset_generation_logs/channel_modeling/environment_elevation_path_distribution_v1_20260826_r1/sampling_contract.json`.

## Global Constraints

- This plan is `Planned / Not started`. Writing it does not fit, sample, execute, or publish an activation model.
- Use only existing 10.23 MHz CSV/JSON/CSV.GZ/model artifacts. Never read raw IQ, invoke MATLAB/SAGE/batch, or process 20.46 MHz.
- Do not modify existing SAGE outputs, Stage0 files, event/path database partitions, model artifacts, metadata, inventory, manifests, requests, handoff history, or QA evidence.
- Keep the completed NLOS parameter model immutable: model manifest SHA-256 `4f24dd3a5532526ef9966288ea7de9d863fabd812abe07a811647095e5368f3c`.
- Keep the completed main/common-gain model immutable: model manifest SHA-256 `6f36dab892622c9b9dc61ecde91fda85ff12ca60eeea4f81fe37760f0acb1e45`.
- Keep `scripts/sage_pipeline/run_nav_sage_pipeline.m` at SHA-256 `bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c`.
- Use the fixed environments `Urban`, `Special Reflective`, `Mountain/Valley`, and `Highway/Open`.
- Use the fixed elevation bands `LOW=[0,30)`, `MID=[30,60)`, and `HIGH=[60,90]` degrees.
- Stage4 labels are the intended model target. Stage1 candidates, Stage2 model order, and Stage3 reliable centers must never be treated as active NLOS labels.
- The learned occurrence quantity is a conservative `Stage4-confirmed-support occupancy proxy`, not physical multipath occurrence probability. A zero-confirmed state is not LOS and is not proof of no physical multipath.
- The conditional multiplicity model uses confirmed multipath paths only. It excludes LOS/reference rows and never equates `L>=2` with confirmed multipath.
- Do not estimate phase, lock-to-amplitude mapping, path lifetime, inter-block persistence, absolute RF power, or a complete channel model in this layer.
- Block policy remains frozen: sample activation and path parameters once at block start and hold them fixed for every millisecond in that block.
- Main path slot 0 remains external to this model. Its default pre-gain tuple remains `[0 ns, 0 Hz, 1]`; the completed common-gain layer is composed later.
- Write future execution output only to new-only `dataset_generation_logs/channel_modeling/nlos_slot_activation_v1_20260826_r1/`. If it exists, stop; do not overwrite, resume, delete, rename, or silently select another directory.
- Update Engineering/Paper Handoffs only after a real build and independent QA. A plan alone changes no project status.

---

## Frozen Evidence Baseline

### Source hashes

| Source | SHA-256 |
|---|---|
| `facts/event_parameters.csv` | `a182c740961dde0fbe9e1df8525ae15bc42e0d4e4992060b77656f45bc2f7e91` |
| `facts/path_parameters.csv` | `2a44913d1c06f78d2748428b1d72f1b4712a6b5d3f33fc598a14fe17a3e3414a` |
| `facts/events.csv` | `b1340bb1f17bb2e52e2857234d61aa084fbc734cf352f32be7bdb4275661c9d1` |
| `facts/event_paths.csv` | `80e0f0eb6a8bcaebb7dd50398994751aa422a0b5e8bd2c2833424d3e3731da2a` |
| `facts/sage_runs.csv` | `f4303749beeb73e922758ef6a1cfb0eef7b4e69d49b2f49ad8b6bf29cb3a7ae5` |
| `exports/run_summary.csv` | `b2251b2393ab6c7545dc444028e00f9d06e4200086d713211be26011a93e7a87` |
| `exports/modeling_run_eligibility.csv` | `163bd5d9ce8cf3d0681e29c46b3d3fac3a9cce92877c3288207c789b6123638e` |
| `facts/event_context_aligned.csv` | `38b5cdc8aedb1c4576952d7e9fd2344b3414f67ddca2443e4a20a63ca813e41f` |
| `common_gain_analysis_grid.csv.gz` | `c5691a42e160e85b5106293499f0ea9e6af96016f27933f29913e8e2e0d8ce09` |

All paths above are relative to their existing versioned partitions/namespaces. The config must record full relative paths and these hashes; basename-only matching is forbidden.

### Population accounting

- Modeling-eligible runs: `63`; excluded legacy runs: exactly one G06 run.
- Valid Stage0 40 ms windows across the 63 eligible runs: `169637`.
- Strict Stage4-confirmed events after the G06 exclusion: `94` in `35` positive runs.
- Zero-confirmed runs under the current criterion: `28`.
- Confirmed NLOS paths: `100`.
- Confirmed path-count distribution: `K=1: 89 events`, `K=2: 4 events`, `K=3: 1 event`.
- Elevation-ready confirmed events/paths: `81/84`; environment-only confirmed events/paths: `13/16`.
- Preliminary unique union of all eligible `center ±2` window IDs: `367` before continuity and geometry eligibility checks. The implementation must recompute this value from frozen sources.

### Conditional multiplicity counts

| Environment | K=1 | K=2 | K=3 | Total events |
|---|---:|---:|---:|---:|
| Urban | 39 | 0 | 1 | 40 |
| Special Reflective | 30 | 3 | 0 | 33 |
| Mountain/Valley | 16 | 1 | 0 | 17 |
| Highway/Open | 4 | 0 | 0 | 4 |

Elevation-ready direct event counts are sparse:

| Environment | LOW | MID | HIGH |
|---|---:|---:|---:|
| Urban | 0 | 28 (`27×K1, 1×K3`) | 10 (`10×K1`) |
| Special Reflective | 19 (`19×K1`) | 1 (`1×K1`) | 2 (`2×K1`) |
| Mountain/Valley | 5 (`5×K1`) | 8 (`7×K1, 1×K2`) | 4 (`4×K1`) |
| Highway/Open | 0 | 3 (`3×K1`) | 1 (`1×K1`) |

These counts show why three independent per-slot Bernoulli fits or cell-specific slot distributions are not supportable.

---

## Alternatives Considered

### Recommended: hierarchical hurdle model

1. Sample `Z_active` from an environment × elevation Stage4-confirmed-support occupancy model.
2. If `Z_active=0`, set `K=0` and leave all three NLOS slots inactive.
3. If `Z_active=1`, sample `K in {1,2,3}` from a separate hierarchical multiplicity model.
4. Activate a deterministic prefix of the fixed slots and draw `K` paths from the already frozen NLOS parameter distribution.

This keeps occurrence evidence separate from conditional path count, preserves the meaning of zero-confirmed exposure, and avoids inventing independent slot identities.

### Rejected: always activate all three NLOS slots

This contradicts the observed event-level multiplicity (`89/94` events contain only one confirmed NLOS path) and would turn fixed storage capacity into a false physical claim.

### Rejected: independent Bernoulli probability for each NLOS slot

The data do not identify stable slot-specific populations. Independent draws can also create noncanonical masks such as `010` or `101`, making slot identity depend on arbitrary labels rather than propagation order.

### Rejected: one direct four-category multinomial over `K=0,1,2,3` per window

`K=1,2,3` is observed only at Stage4-confirmed event centers, while `K=0` would come from all Stage0 exposure. Combining these without a hurdle conflates two different observation processes and overstates the meaning of unconfirmed windows.

---

## Frozen Scientific Design

### 1. Block-level state

For a simulation block `b` with environment `e` and elevation band `h`:

```text
Z_b ~ Bernoulli(p_active[e,h])

if Z_b = 0:
    K_b = 0
if Z_b = 1:
    K_b ~ Categorical(q_1[e,h], q_2[e,h], q_3[e,h])
```

The mask is deterministic given `K_b`:

| K | Slot 1 | Slot 2 | Slot 3 |
|---:|---:|---:|---:|
| 0 | 0 | 0 | 0 |
| 1 | 1 | 0 | 0 |
| 2 | 1 | 1 | 0 |
| 3 | 1 | 1 | 1 |

The mask remains fixed throughout the block. This v1 model does not create within-block births/deaths and does not learn persistence between consecutive blocks.

### 2. Stage4-confirmed-support occupancy evidence

- Build exposure from every valid Stage0 window in the 63 modeling-eligible runs.
- Resolve each Stage0 source from `sage_runs.csv.source_result_relpath`; do not search by scene/PRN naming guesses.
- Join a Stage0 window to the frozen 20 ms common-gain geometry grid by identical `run_id` and nearest `recording_time_s/time_s` within `0.011 s`.
- Require a unique nearest row. At an exact tie, select the lower `time_bin_index` and record `tie_break=lower_time_bin_index`.
- Do not interpolate geometry. Cell-level exposure requires `geometry_join_valid=1`; environment-parent exposure may retain geometry-invalid rows because environment is verified independently.
- A strict confirmed event contributes a core label only at `center_window_id`.
- The activation-support set is the unique union of `center_window_id ±2`, constrained to existing Stage0 windows in the same continuity segment. Overlapping closures are unioned, never counted repeatedly.
- Continuity must be checked from sample/TOW progression. No closure may cross a sample discontinuity, TOW discontinuity, missing window, or run boundary.
- Save separate `CONFIRMED_CORE` and `CONFIRMED_CLOSURE_ONLY` provenance. The selected occupancy label is their union.

The selected probability is named `p_stage4_confirmed_support_active`. Reports and downstream code must not shorten it to an unqualified physical `multipath_probability`.

### 3. Scene-balanced hierarchical occupancy estimator

Raw 20 ms/40 ms windows are strongly correlated. Therefore raw window count must not be treated as an independent binomial sample size for uncertainty.

For every scene and cell with direct exposure, compute:

```text
r_scene_cell = unique_confirmed_support_windows / valid_exposure_windows
```

Fit a deterministic Beta pseudo-posterior using equal scene weight:

1. Base prior: `Beta(0.5, 0.5)`.
2. Global parent: one fractional success/failure observation per represented scene.
3. Environment parent: direct scene fractions plus `8.0` pseudo-scenes at the global-parent mean.
4. Cell model: direct scene-cell fractions plus `8.0` pseudo-scenes at the environment-parent mean.
5. Selected probability: posterior mean `alpha/(alpha+beta)`.
6. Save the 2.5%, 50%, and 97.5% Beta quantiles.

Also save the raw time-weighted fraction `total_support_windows/total_exposure_windows` as a diagnostic only. It is not the generator-selected probability because long scenes and scenes with many PRNs must not dominate silently.

Occurrence support statuses:

- `DATA_SUPPORTED_WITH_GROUPED_VALIDATION`: at least 10 confirmed core events from at least 2 scenes.
- `SPARSE_PARTIAL_POOLING`: at least 1 confirmed core event but below the grouped threshold.
- `EXPOSURE_ONLY_ZERO_CONFIRMED`: valid direct exposure exists but no confirmed core event; zero-confirmation updates the occupancy estimate but is not a physical no-multipath label.
- `PRIOR_ONLY`: no valid direct exposure for that environment × elevation cell.

### 4. Hierarchical conditional multiplicity estimator

Use event-level `confirmed_path_count` only; do not replicate K over closure windows.

1. Categories are fixed to `[1,2,3]`.
2. Reject any source event with `K<1` or `K>3`; never truncate or merge paths.
3. Base Dirichlet prior is `alpha0=[0.5,0.5,0.5]`.
4. Global posterior uses all 94 modeling-ready confirmed events.
5. Environment parents use all confirmed events in that environment, including the 13 elevation-ineligible events.
6. Each environment posterior receives prior-equivalent mass `8.0` in the global posterior proportions.
7. Each non-empty cell posterior receives prior-equivalent mass `8.0` in its environment-parent proportions.
8. An empty cell copies its environment parent exactly and is `PRIOR_ONLY` for multiplicity.

Multiplicity support statuses match the existing path-distribution layer:

- `DATA_SUPPORTED_WITH_GROUPED_VALIDATION`: `n_event>=10` and `n_scene>=2`.
- `SPARSE_PARTIAL_POOLING`: `3<=n_event<10`.
- `PRIOR_DOMINANT`: `1<=n_event<=2`.
- `PRIOR_ONLY`: `n_event=0`.

No K-specific delay/Doppler/power distribution is fitted: only five of 94 events have `K>1`. Active path parameters continue to come from the frozen environment × elevation joint NLOS model.

### 5. Deterministic slot identity

Fixed slot capacity is not a physical label. For every observed event or generated draw set, canonical ordering is:

1. ascending `relative_delay_ns`;
2. descending `relative_amplitude_linear`;
3. ascending signed `relative_doppler_hz`;
4. ascending stable source `path_id`/draw index.

The ordered paths receive `NLOSPathID=1,2,3`. Slot 1 therefore means earliest active NLOS path, not strongest path and not a persistent physical reflector identity across blocks.

### 6. Inactive-slot semantics

The canonical internal table must include `PathActive` and `PathStatus`, even if a later hardware export adapter requires the user's seven-column table.

For an inactive NLOS slot:

```text
PathActive = 0
PathStatus = INACTIVE_NO_PATH
RelativeAmplitude = 0.0
RelativeDelay = null
RelativeDoppler = null
RelativePhase_rad = null
```

Zero must not replace missing delay/Doppler/phase because that would fabricate a valid zero-offset propagation path. If the final equipment format cannot carry null/status fields, the later generator must emit a sidecar status table and document the amplitude-zero encoding.

### 7. Generator-facing modes

The activation contract exposes two explicit modes; no silent fallback is permitted:

- `EMPIRICAL_CONFIRMED_SUPPORT`: sample `Z_b` from the bounded occupancy proxy, then sample K.
- `CONDITIONAL_ACTIVE_STRESS`: externally force `Z_b=1`, then sample K. This is an engineering stress-test assumption and must be labeled as such.

The first mode is the scientific default. The second mode is permitted only when the caller deliberately requests a multipath-active test block.

### 8. Generator-facing interface

The later generator consumes one explicit request per simulation block:

```text
ActivationRequest(
    environment_class,
    elevation_band,
    block_id,
    block_length_ms,
    master_seed,
    activation_mode
)
```

It receives one immutable state:

```text
BlockActivationState(
    Z_active,
    K_active,
    active_mask,
    occupancy_support_status,
    multiplicity_support_status,
    model_provenance
)
```

`block_length_ms` controls repetition only; it does not alter the fitted probability. The state is sampled once and repeated for all `ms=1..block_length_ms`. The final export maps `LOW/MID/HIGH` to the requested `SatelliteID=Low/Mid/High`; this label is an elevation context, not a physical PRN identifier.

### 9. Provenance propagation

Every sampled block must carry:

```text
activation_model_id
activation_model_manifest_sha256
activation_mode
environment_class
elevation_band
occupancy_support_status
multiplicity_support_status
path_parameter_support_status
combined_support_status
is_prior_only
master_seed
block_seed
Z_active
K_active
active_mask
```

`combined_support_status` is the most conservative of occupancy, multiplicity, and frozen path-parameter support. A cell inherited by any required layer must propagate `is_prior_only=true`.

### 10. Uncertainty and deterministic QA draws

- Scene-block bootstrap: 1000 replicates, seed `20260828`; resample complete scenes, never individual windows/events.
- QA draws: 4096 blocks per cell in each activation mode, seed `20260829`.
- Use separate deterministic RNG streams for occurrence, K, and future path draws, derived from `(master_seed, environment, elevation, block_id, stream_name)` with SHA-256. Draw order in another cell must not change a cell's samples.
- For empirical QA, observed frequencies must fall within `max(0.02, 5*sqrt(p*(1-p)/4096))` of the analytic probability.
- Sparse one-scene cells report `GROUPED_GENERALIZATION_NOT_ESTIMABLE`; they must not be called validated.

---

## Planned File Structure

| File | Responsibility |
|---|---|
| `configs/channel_modeling/nlos_slot_activation_v1.json` | Freeze all input paths/hashes, hierarchy constants, closure/join rules, seeds, namespace and prohibitions. |
| `scripts/analysis/channel_modeling/nlos_slot_activation_core.py` | Pure source loading, exposure construction, hurdle fitting, slot mapping and deterministic sampling primitives. |
| `scripts/analysis/channel_modeling/build_nlos_slot_activation_model.py` | Validate-only/new-only builder and immutable artifact publication. |
| `scripts/analysis/channel_modeling/audit_nlos_slot_activation_model.py` | Independent source/model/slot/provenance auditor; must not call builder fit functions. |
| `scripts/analysis/channel_modeling/tests/test_nlos_slot_activation_core.py` | Core unit and scientific-contract tests. |
| `scripts/analysis/channel_modeling/tests/test_build_nlos_slot_activation_model.py` | Builder, hash, namespace and schema tests. |
| `scripts/analysis/channel_modeling/tests/test_audit_nlos_slot_activation_model.py` | Independent tamper/fail-closed tests. |
| `docs/NLOS_SLOT_ACTIVATION_MODEL_V1_REPORT.md` | Result report created only after real build and QA. |

---

### Task 1: Freeze the source and model configuration contract

**Files:**
- Create: `configs/channel_modeling/nlos_slot_activation_v1.json`
- Create: `scripts/analysis/channel_modeling/nlos_slot_activation_core.py`
- Create: `scripts/analysis/channel_modeling/tests/test_nlos_slot_activation_core.py`

**Interfaces:**
- `load_activation_config(path: Path) -> ActivationConfig`
- `verify_frozen_sources(project_root: Path, config: ActivationConfig) -> SourceAudit`
- `load_confirmed_events(project_root: Path, config: ActivationConfig) -> list[ConfirmedEvent]`

- [ ] **Step 1: Write a failing source-contract test.**

```python
def test_frozen_source_contract(project_root, config_path):
    config = load_activation_config(config_path)
    audit = verify_frozen_sources(project_root, config)
    events = load_confirmed_events(project_root, config)
    assert audit.eligible_run_count == 63
    assert audit.stage0_window_count == 169637
    assert len(events) == 94
    assert sum(e.confirmed_path_count for e in events) == 100
    assert Counter(e.confirmed_path_count for e in events) == {1: 89, 2: 4, 3: 1}
```

Also reject changed hashes, G06 inclusion, non-10.23 MHz runs, Stage2/Stage3 labels, `joint_valid!=1`, missing multipath path rows, or a count outside 1–3.

- [ ] **Step 2: Run the focused test and confirm RED.**

```powershell
D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe -m pytest scripts\analysis\channel_modeling\tests\test_nlos_slot_activation_core.py -q
```

Expected: missing config/interfaces.

- [ ] **Step 3: Create the frozen JSON config.** Record source paths/hashes, environment/bin order, 11 ms join tolerance, ±2 closure, Beta/Dirichlet priors, pseudo-scene/event mass 8.0, support thresholds, slot ordering, inactive semantics, seeds, output namespace, protected pipeline hash, and all no-execution flags.
- [ ] **Step 4: Implement strict loaders and cross-check `event_parameters.csv` against `events.csv` plus `event_paths.csv`.** Stage4 labels are target data, not selector tuning.
- [ ] **Step 5: Re-run the focused test and confirm GREEN.**
- [ ] **Step 6: Commit only Task 1 files after reviewing unrelated dirty changes.**

### Task 2: Build the valid Stage0 exposure grid

**Files:**
- Modify: `scripts/analysis/channel_modeling/nlos_slot_activation_core.py`
- Modify: `scripts/analysis/channel_modeling/tests/test_nlos_slot_activation_core.py`

**Interfaces:**
- `resolve_stage0_sources(project_root: Path, audit: SourceAudit) -> list[Stage0Source]`
- `load_stage0_exposure(source: Stage0Source) -> list[ExposureWindow]`
- `join_geometry_grid(exposure, gain_grid_path, tolerance_s=0.011) -> GeometryJoinResult`
- `assign_continuity_segments(windows) -> list[ExposureWindow]`

- [ ] **Step 1: Write failing tests for exact run/source resolution.** Assert `source_result_relpath/stage0_valid_40ms_windows.csv` exists for all 63 eligible runs, hashes are recorded, rows reconcile to each run's `stage0_window_count`, and the total is 169637.
- [ ] **Step 2: Write failing nearest-grid tests.** Cover slash/case-safe run identity, nearest unique join, exact-tie lower-bin rule, 11 ms boundary acceptance, >11 ms rejection, geometry-invalid retention for environment parents, and no interpolation.
- [ ] **Step 3: Write failing continuity tests.** Adjacent window IDs with a sample/TOW gap must receive different segment IDs; valid overlapping 40 ms windows remain in one segment.
- [ ] **Step 4: Run the tests and confirm RED.**
- [ ] **Step 5: Implement streaming GZIP grid indexing by run.** Do not decompress into an unversioned temporary artifact; peak memory and row counts must be recorded.
- [ ] **Step 6: Implement source/hash receipts and deterministic joins.** Preserve null elevation for geometry-invalid windows; do not impute a PRN mean.
- [ ] **Step 7: Re-run tests and confirm GREEN.**
- [ ] **Step 8: Commit Task 2 files only.**

### Task 3: Construct strict core and ±2 closure activation evidence

**Files:**
- Modify: `scripts/analysis/channel_modeling/nlos_slot_activation_core.py`
- Modify: `scripts/analysis/channel_modeling/tests/test_nlos_slot_activation_core.py`

**Interfaces:**
- `build_activation_labels(exposure, events, closure_radius=2) -> ActivationEvidence`
- `aggregate_scene_cell_exposure(evidence) -> list[SceneCellExposure]`

- [ ] **Step 1: Write failing identity/closure tests.** Require 94 unique core event IDs, 100 paths, no duplicate run/window core, and preliminary unique closure union 367.
- [ ] **Step 2: Write overlapping-closure tests.** Two centers whose ±2 neighborhoods overlap must produce one unique exposure-window union while preserving both source event IDs in a normalized membership table.
- [ ] **Step 3: Write boundary/gap tests.** Closure expansion stops at run boundaries and continuity breaks; it must never synthesize a missing Stage0 window.
- [ ] **Step 4: Write semantic tests.** Rejected Stage4 rows, Stage3 reliable centers without Stage4 confirmation, and Stage2 `L>=2` cannot activate any window.
- [ ] **Step 5: Run tests and confirm RED.**
- [ ] **Step 6: Implement `INACTIVE`, `CONFIRMED_CORE`, and `CONFIRMED_CLOSURE_ONLY` labels plus normalized event-membership provenance.**
- [ ] **Step 7: Re-run tests and confirm GREEN.**
- [ ] **Step 8: Commit Task 3 files only.**

### Task 4: Fit the scene-balanced occupancy hierarchy

**Files:**
- Modify: `scripts/analysis/channel_modeling/nlos_slot_activation_core.py`
- Modify: `scripts/analysis/channel_modeling/tests/test_nlos_slot_activation_core.py`

**Interfaces:**
- `fit_beta_pseudo_posterior(scene_rates, parent_mean, parent_mass) -> BetaOccupancyModel`
- `fit_occupancy_hierarchy(scene_cell_exposure, config) -> OccupancyHierarchy`
- `classify_occupancy_support(exposure_scene_count, confirmed_event_count) -> str`

- [ ] **Step 1: Write failing analytic tests.** Verify `Beta(0.5,0.5)` base prior, equal scene weight, exact 8.0 parent pseudo-scene mass, finite `alpha/beta`, normalized mean, and ordered 95% interval.
- [ ] **Step 2: Write a long-scene dominance test.** Replicating every window in one scene must change the time-weighted diagnostic but not the selected scene-balanced posterior.
- [ ] **Step 3: Write zero-confirmed semantics tests.** A cell with exposure but no confirmed core must be `EXPOSURE_ONLY_ZERO_CONFIRMED`, update with zero direct fractions, and never be labeled LOS; a cell with no exposure must copy its environment parent and be `PRIOR_ONLY`.
- [ ] **Step 4: Run tests and confirm RED.**
- [ ] **Step 5: Implement global → environment → cell occupancy fitting.** Persist direct scene count, exposure windows, support windows, core events, time-weighted fraction, posterior parameters/intervals, parent IDs, and support status.
- [ ] **Step 6: Re-run tests and confirm GREEN.**
- [ ] **Step 7: Commit Task 4 files only.**

### Task 5: Fit conditional path-count probabilities

**Files:**
- Modify: `scripts/analysis/channel_modeling/nlos_slot_activation_core.py`
- Modify: `scripts/analysis/channel_modeling/tests/test_nlos_slot_activation_core.py`

**Interfaces:**
- `fit_dirichlet_counts(counts, parent_probabilities, parent_mass) -> MultiplicityModel`
- `fit_multiplicity_hierarchy(events, config) -> MultiplicityHierarchy`
- `sample_path_count(model: MultiplicityModel, rng: Generator) -> int`

- [ ] **Step 1: Write failing global-count tests.** Require exact counts `[89,4,1]`, positive probabilities for all K categories, sum equal to 1 within `1e-12`, and no K=0 category inside the conditional model.
- [ ] **Step 2: Write failing hierarchy tests.** Confirm environment parents include elevation-ineligible events, cell likelihoods use only 81 elevation-ready events, parent mass is exactly 8.0, and empty cells equal their environment parent.
- [ ] **Step 3: Write support-status tests.** Cover all four status classes and verify zero-event cells are `PRIOR_ONLY` for multiplicity even when occurrence exposure exists.
- [ ] **Step 4: Write fail-closed tests for K=4, negative counts, duplicate event IDs, and event/path count disagreement.**
- [ ] **Step 5: Run tests and confirm RED.**
- [ ] **Step 6: Implement deterministic Dirichlet posterior parameters, means, 95% intervals, and categorical sampling.**
- [ ] **Step 7: Re-run tests and confirm GREEN.**
- [ ] **Step 8: Commit Task 5 files only.**

### Task 6: Implement the fixed-slot mapper and internal output contract

**Files:**
- Modify: `scripts/analysis/channel_modeling/nlos_slot_activation_core.py`
- Modify: `scripts/analysis/channel_modeling/tests/test_nlos_slot_activation_core.py`

**Interfaces:**
- `activation_mask(k: int) -> tuple[bool, bool, bool]`
- `canonicalize_paths(paths: Sequence[PathDraw]) -> list[SlottedPath]`
- `emit_internal_slot_rows(block: BlockState, paths: Sequence[PathDraw]) -> list[SlotRow]`

- [ ] **Step 1: Write exact-mask tests.** Assert `0→000`, `1→100`, `2→110`, `3→111`; reject any other K.
- [ ] **Step 2: Write deterministic-order tests.** Cover delay ordering and every tie-break in sequence. Reordering input rows must not change assigned NLOSPathIDs.
- [ ] **Step 3: Write inactive-null tests.** Require amplitude 0 with null delay/Doppler/phase plus `INACTIVE_NO_PATH`; reject an inactive row containing nonzero amplitude or finite propagation parameters.
- [ ] **Step 4: Write four-row internal-schema tests.** Every millisecond has path IDs `0,1,2,3` exactly once; slot 0 remains outside activation decisions and keeps its external main-gain provenance.
- [ ] **Step 5: Run tests and confirm RED.**
- [ ] **Step 6: Implement the mapper without fitting slot-specific parameter distributions.** Active NLOS parameters are consumed from the frozen path model; conditionally IID draws are sorted only after sampling.
- [ ] **Step 7: Re-run tests and confirm GREEN.**
- [ ] **Step 8: Commit Task 6 files only.**

### Task 7: Add deterministic streams, bootstrap uncertainty, and QA draws

**Files:**
- Modify: `scripts/analysis/channel_modeling/nlos_slot_activation_core.py`
- Modify: `scripts/analysis/channel_modeling/tests/test_nlos_slot_activation_core.py`

**Interfaces:**
- `derive_stream_seed(master_seed, environment, elevation, block_id, stream_name) -> int`
- `scene_block_bootstrap(evidence, events, config) -> BootstrapResult`
- `generate_activation_qa_draws(model, config) -> list[QADrawSummary]`

- [ ] **Step 1: Write seed-isolation tests.** The same cell/block/stream must reproduce exactly; drawing another cell first must not alter it; occurrence and K streams must differ.
- [ ] **Step 2: Write grouped-bootstrap tests.** Assert 1000 complete-scene replicates, seed 20260828, no row/window resampling, and explicit failure receipts rather than silent replicate replacement.
- [ ] **Step 3: Write predictive-frequency tests.** For each of 12 cells and both modes, verify analytic versus 4096-draw activation and K frequencies using the frozen Monte Carlo tolerance.
- [ ] **Step 4: Write prior-provenance tests.** QA draws from inherited cells must carry parent and `PRIOR_ONLY` lineage.
- [ ] **Step 5: Run tests and confirm RED.**
- [ ] **Step 6: Implement bootstrap intervals and deterministic QA summaries.** Do not emit final simulator rows in this task.
- [ ] **Step 7: Re-run tests and confirm GREEN.**
- [ ] **Step 8: Commit Task 7 files only.**

### Task 8: Implement the new-only builder and immutable artifact schema

**Files:**
- Create: `scripts/analysis/channel_modeling/build_nlos_slot_activation_model.py`
- Create: `scripts/analysis/channel_modeling/tests/test_build_nlos_slot_activation_model.py`

**Interfaces:**
- `build_activation_model(project_root: Path, config_path: Path, output_dir: Path) -> BuildReceipt`
- CLI: `--project-root`, `--config`, `--output`, optional `--validate-only`

- [ ] **Step 1: Write failing preflight/new-only tests.** Reject an existing output directory without modifying it; reject output under `scenes`, `sage_results`, prior model namespaces, or `_trash`; reject changed source/config/model/pipeline hashes before output creation.
- [ ] **Step 2: Write required-artifact tests.** Require exactly the declared schemas for:

```text
source_preflight.csv
stage0_source_manifest.csv
activation_exposure_grid.csv.gz
confirmed_support_membership.csv
scene_cell_exposure.csv
cell_occupancy_parameters.csv
multiplicity_event_catalog.csv
cell_multiplicity_parameters.csv
observed_slot_assignment_audit.csv
bootstrap_uncertainty.csv
qa_draw_summary.csv
slot_activation_contract.json
nlos_slot_activation_model.json
model_manifest.json
model_report.md
build_receipt.json
```

- [ ] **Step 3: Run builder tests and confirm RED.**
- [ ] **Step 4: Implement `--validate-only`.** It must verify all hashes, 63/169637/94/100 accounting, output absence, backend receipt, and no-execution flags without creating the output directory.
- [ ] **Step 5: Implement atomic new-only publication.** Record every Stage0 source hash, all source/model/config/script/backend hashes, counts, hierarchy parameters, support status, output hashes, runtime and memory.
- [ ] **Step 6: Freeze `slot_activation_contract.json`.** Include state equations, two explicit modes, K/mask map, sorting, inactive semantics, block-fixed policy, support propagation and downstream phase/lock deferrals.
- [ ] **Step 7: Re-run builder tests and confirm GREEN.**
- [ ] **Step 8: Commit Task 8 files only.**

### Task 9: Implement independent activation-model QA

**Files:**
- Create: `scripts/analysis/channel_modeling/audit_nlos_slot_activation_model.py`
- Create: `scripts/analysis/channel_modeling/tests/test_audit_nlos_slot_activation_model.py`

**Interfaces:**
- `audit_activation_model(project_root: Path, config_path: Path, model_dir: Path) -> AuditResult`
- CLI: `--project-root`, `--config`, `--model-dir`

- [ ] **Step 1: Write independent tamper tests.** Reject changed source/Stage0 hashes, G06 inclusion, Stage3-only activation, duplicate closure counting, geometry imputation, raw-window binomial precision, changed K counts, non-prefix masks, non-null inactive paths, output hash changes, and protected-pipeline changes.
- [ ] **Step 2: Write builder-independence test.** The auditor must recompute accounting and probability normalization without importing builder fit functions.
- [ ] **Step 3: Run auditor tests and confirm RED.**
- [ ] **Step 4: Implement independent source, exposure, occupancy, multiplicity, slot, deterministic-draw, hash and namespace checks.**
- [ ] **Step 5: Emit fixed gates.**

```text
SOURCE_PROVENANCE_GATE = PASS/FAIL
STAGE4_LABEL_GATE = PASS/FAIL
EXPOSURE_AND_CLOSURE_GATE = PASS/FAIL
OCCUPANCY_MODEL_GATE = PASS_WITH_LIMITATIONS/FAIL
MULTIPLICITY_MODEL_GATE = PASS_WITH_LIMITATIONS/FAIL
SLOT_CONTRACT_GATE = PASS/FAIL
DETERMINISM_GATE = PASS/FAIL
NAMESPACE_AND_HASH_GATE = PASS/FAIL
MODEL_QA = PASS_WITH_LIMITATIONS/FAIL
READY_FOR_GENERATOR_COMPOSITION = YES/NO
```

`PASS_WITH_LIMITATIONS` is expected when hard gates pass because the output remains a Stage4-confirmed-support proxy with sparse/prior-only cells. It must never be reported as a universal physical occurrence model.

- [ ] **Step 6: Re-run auditor tests and confirm GREEN.**
- [ ] **Step 7: Commit Task 9 files only.**

### Task 10: Execute the first Python-only build and independent QA

**Runtime output:** `dataset_generation_logs/channel_modeling/nlos_slot_activation_v1_20260826_r1/`

- [ ] **Step 1: Run static compilation and focused tests.**

```powershell
D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe -m py_compile scripts\analysis\channel_modeling\nlos_slot_activation_core.py scripts\analysis\channel_modeling\build_nlos_slot_activation_model.py scripts\analysis\channel_modeling\audit_nlos_slot_activation_model.py
D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe -m pytest scripts\analysis\channel_modeling\tests\test_nlos_slot_activation_core.py scripts\analysis\channel_modeling\tests\test_build_nlos_slot_activation_model.py scripts\analysis\channel_modeling\tests\test_audit_nlos_slot_activation_model.py -q
```

- [ ] **Step 2: Run validation-only.** Require source/model/pipeline hashes, expected counts, output absence, and `raw_iq_read=false`, `matlab=false`, `sage=false`, `batch=false`, `process_20_46_mhz=false`.
- [ ] **Step 3: Execute exactly once only after explicit user authorization.**

```powershell
D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe scripts\analysis\channel_modeling\build_nlos_slot_activation_model.py --project-root E:\GNSS_Multipath_Project --config E:\GNSS_Multipath_Project\configs\channel_modeling\nlos_slot_activation_v1.json --output E:\GNSS_Multipath_Project\dataset_generation_logs\channel_modeling\nlos_slot_activation_v1_20260826_r1
```

- [ ] **Step 4: Run independent QA.**

```powershell
D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe scripts\analysis\channel_modeling\audit_nlos_slot_activation_model.py --project-root E:\GNSS_Multipath_Project --config E:\GNSS_Multipath_Project\configs\channel_modeling\nlos_slot_activation_v1.json --model-dir E:\GNSS_Multipath_Project\dataset_generation_logs\channel_modeling\nlos_slot_activation_v1_20260826_r1
```

- [ ] **Step 5: Apply the hard acceptance gate.** Readiness may be YES only if source counts/hashes reconcile; all 12 cells have explicit occupancy/multiplicity records; closure union and overlap ownership are correct; probabilities normalize; sparse/prior statuses are propagated; masks/slot identities are deterministic; inactive semantics are unambiguous; QA draws reproduce; and no protected artifact changed.

If any hard gate fails, preserve r1 as an immutable failed experiment and stop. A scientific-rule change requires v2 and a new namespace; never tune r1 in place.

### Task 11: Report and synchronize status after real QA

**Files:**
- Create after QA only: `docs/NLOS_SLOT_ACTIVATION_MODEL_V1_REPORT.md`
- Modify after QA only: `docs/GNSS_SAGE_ENGINEERING_HANDOFF_CURRENT.md`
- Modify after QA only: `docs/GNSS_SAGE_PAPER_HANDOFF_CURRENT.md`

- [ ] **Step 1: Write the result report from immutable outputs.** Include all hashes, exposure/closure accounting, occupancy and K tables, cell support, uncertainty, slot contract, deterministic QA, and limitations.
- [ ] **Step 2: Update Engineering Handoff.** Mark this layer Completed/Failed exactly according to QA; keep phase/lock mapping and the full generator unstarted.
- [ ] **Step 3: Update Paper Handoff only with bounded scientific language.** Never write that physical occurrence probability or a complete statistical channel model has been established.
- [ ] **Step 4: Leave `PAPER_WORKSPACE_INDEX.md` unchanged unless the paper asset structure changes.**
- [ ] **Step 5: Run final verification.**

```powershell
git diff --check -- configs/channel_modeling scripts/analysis/channel_modeling docs/NLOS_SLOT_ACTIVATION_MODEL_V1_REPORT.md docs/GNSS_SAGE_ENGINEERING_HANDOFF_CURRENT.md docs/GNSS_SAGE_PAPER_HANDOFF_CURRENT.md
D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe -m pytest scripts\analysis\channel_modeling\tests -q
Get-FileHash E:\GNSS_Multipath_Project\scripts\sage_pipeline\run_nav_sage_pipeline.m -Algorithm SHA256
```

Expected protected hash: `BFFC123C97AF77F0A797F417D3866E9A34FEAB7729C5C1575352F53BC3571B9C`.

---

## Explicitly Deferred Follow-On Work

1. Mapping receiver lock state to path-0/NLOS amplitude, phase reset/continuity, and recovery envelopes.
2. Phase initialization `Uniform(-pi,pi)` and Doppler-continuous phase evolution in the millisecond generator.
3. Inter-block path lifetime, birth/death memory, and correlated activation transitions.
4. Composition of main/common gain, NLOS path parameters, slot activation and lock diagnostics.
5. The reproducible final four-row-per-ms generator and its export adapter/QA.
6. Absolute RF power/darkroom equipment calibration.
7. 20.46 MHz adaptation.

## Completion Boundary

This plan produces only the fixed three-NLOS-slot activation layer:

```text
environment × elevation
  -> bounded Stage4-confirmed-support occupancy state Z
  -> conditional confirmed path count K in {1,2,3}
  -> canonical active mask over NLOS slots 1–3
```

It does not produce the final simulation table. After this layer passes QA, the remaining route is:

```text
lock state -> amplitude/phase/recovery mapping
  -> compose main gain + NLOS parameter model + slot activation
  -> reproducible four-path millisecond generator
  -> independent generator QA
```

## Self-Review Checklist

- [ ] The plan separates occurrence-state evidence from conditional path count.
- [ ] `p_stage4_confirmed_support_active` is never mislabeled as physical multipath probability.
- [ ] Exact 63/169637/94/100 and 89/4/1 source accounting is frozen.
- [ ] Zero-confirmed exposure is not called LOS; no-exposure and no-event semantics are distinct.
- [ ] Environment parents may use geometry-ineligible events; cell fits may not.
- [ ] K is sampled jointly; three independent slot Bernoulli models are forbidden.
- [ ] Fixed slots use deterministic delay-based ordering and prefix masks.
- [ ] Inactive slots cannot masquerade as valid zero-offset paths.
- [ ] Main gain, phase, lock mapping, lifetime and final generation remain out of scope.
- [ ] Every sparse/prior contribution propagates to the downstream block provenance.
- [ ] New-only publication and independent QA detect semantic drift and tampering.
- [ ] Handoffs change only after a real build and QA.
