# Environment × Elevation Path-Distribution Model v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and independently validate one auditable joint NLOS path-parameter distribution for every `environment_class × elevation_band` cell, using only existing Stage4-confirmed path parameters and explicit hierarchical priors for sparse or empty cells.

**Architecture:** A standalone Python package will consume the frozen Stage4 path-parameter partition, select one global marginal family per physical parameter using scene-grouped validation, and estimate environment/cell parameters through deterministic hierarchical partial pooling. Each of the 12 cells will combine three cell-specific marginals with an environment-level Gaussian copula; zero-observation cells inherit the environment parent model and are marked `PRIOR_ONLY`. A separate auditor independently verifies eligibility, transforms, support classes, normalization, deterministic sampling, hashes and namespace isolation.

**Tech Stack:** Python 3.12; NumPy 2.5.1; SciPy 1.18.0; OpenBLAS from `D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe`; standard-library CSV/JSON/hash/dataclass/path utilities; pytest. No dependency installation is permitted.

**Spec:** Approved active modeling contract; `docs/paper_draft/GNSS_MULTIPATH_DATABASE_SCHEMA.md`; `docs/ENVIRONMENT_CONDITIONED_LOCK_MODEL_V1_REPORT.md`; `dataset/multipath_event_database/v1/partitions/parameter_set_id=parameters_20260825_stage4_path_v1/parameter_manifest.json`.

## Global Constraints

- This plan is `Planned / Not started`; writing it does not start fitting.
- Consume only `facts/path_parameters.csv` from `parameters_20260825_stage4_path_v1`; required SHA-256 is `2a44913d1c06f78d2748428b1d72f1b4712a6b5d3f33fc598a14fe17a3e3414a`.
- Accept only `estimate_stage=stage4_joint`, `path_role=multipath`, `is_multipath=1`, `label_value=confirmed_multipath`, `environment_modeling_ready=1` and finite delay/Doppler/power rows.
- Use all 100 environment-ready paths for global/environment parents. Use only the 84 rows with `elevation_modeling_ready=1`, `geometry_join_valid=1` and `LOW/MID/HIGH` as direct cell observations.
- The 16 geometry-ineligible paths may inform environment/global parents only. Never assign or impute their elevation.
- Frozen bins: `LOW=[0,30)`, `MID=[30,60)`, `HIGH=[60,90]` degrees.
- Frozen environments: `Urban`, `Special Reflective`, `Mountain/Valley`, `Highway/Open`.
- Model confirmed NLOS parameters only. Do not fit LOS/reference paths, occurrence rate, path count, path lifetime, main gain, phase, lock depth or absolute RF power.
- Output variables are `relative_delay_ns`, signed `relative_doppler_hz`, and `relative_amplitude_linear`. Fit power in dB; convert with `10 ** (relative_power_db / 20)`.
- Do not clip positive relative-power values. A generated NLOS amplitude may exceed one because path 0 is a reference, not guaranteed physical LOS or strongest path.
- Phase remains the external assumption `Uniform(-pi, pi)` plus Doppler-continuous evolution; it is not fitted here.
- The fixed four-row millisecond table and three-NLOS-slot policy are outside this plan. Publish a sampling contract only.
- Never read raw IQ, invoke MATLAB/SAGE/batch, process 20.46 MHz, or alter SAGE outputs, metadata, inventory, source partitions or the lock model.
- Write only to new-only `dataset_generation_logs/channel_modeling/environment_elevation_path_distribution_v1_20260826_r1/`. If it exists, stop; do not overwrite, resume, delete or silently choose another namespace.
- Keep `scripts/sage_pipeline/run_nav_sage_pipeline.m` at SHA-256 `bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c`.
- Update handoffs only after a real fit and independent QA. A plan alone changes no model status.

---

## Frozen Coverage Matrix

Counts are elevation-ready Stage4-confirmed multipath paths:

| Environment | LOW | MID | HIGH |
|---|---:|---:|---:|
| Urban | 0 `PRIOR_ONLY` | 30 | 10 |
| Special Reflective | 19 | 1 | 2 |
| Mountain/Valley | 5 | 9 | 4 |
| Highway/Open | 0 `PRIOR_ONLY` | 3 | 1 |

The ten observed cells sum to 84 paths. Support status is frozen as:

- `DATA_SUPPORTED_WITH_GROUPED_VALIDATION`: `n_path >= 10` and `n_scene >= 2`;
- `SPARSE_PARTIAL_POOLING`: `3 <= n_path < 10`;
- `PRIOR_DOMINANT`: `1 <= n_path <= 2`;
- `PRIOR_ONLY`: `n_path = 0`.

These labels describe model support, not physical multipath prevalence.

## Frozen Scientific Design

### Marginals

- Delay candidates: lognormal, Gamma, Weibull; location fixed at zero and support strictly positive.
- Signed Doppler candidates: Student-t, normal, Laplace.
- Relative-power-dB candidates: Student-t, normal, Laplace; convert to linear amplitude only on export/sampling.
- Select one global family per parameter using leave-one-scene-out held-out log likelihood across all 11 represented scenes.
- Candidate order above is the deterministic tie-break order; absolute tie tolerance is `1e-9`. A failed/non-finite fold invalidates a family and must be recorded.

### Hierarchical partial pooling

For each selected family:

1. Fit a global parent from all 100 environment-ready paths.
2. Fit each environment parent from every path in that environment, including elevation-ineligible rows, regularized by global pseudo-observations.
3. Fit each non-empty cell from its direct elevation-ready rows, regularized by environment pseudo-observations.
4. For an empty cell, copy the environment parent exactly and set `PRIOR_ONLY`, `local_likelihood_row_count=0`, `parameter_source=environment_parent_only`.

Use 64 deterministic parent quantiles at `(j-0.5)/64`, `j=1..64`, with total prior-equivalent weight 8.0 at both hierarchy levels. Each pseudo-observation has weight `8/64`; each real row has weight 1. Do not tune these weights after viewing cell outcomes.

### Joint dependence

- Use a Gaussian copula over delay, signed Doppler and power dB.
- Estimate global Spearman correlation from all 100 paths and convert with `rho_gaussian = 2*sin(pi*rho_spearman/6)`.
- Estimate each environment correlation and shrink toward global with `w=n_environment/(n_environment+10)`.
- Project to a correlation matrix by eigenvalue clipping at `1e-6`, renormalize the diagonal, and record correction norm.
- Every cell references its environment copula. Do not estimate cell-specific covariance in v1.

This yields one joint distribution per cell without inventing covariance from one or two paths. Dependence among the future three NLOS slots is not learned; the later generator may use conditionally IID joint draws, but must label that as an engineering assumption.

### Uncertainty and QA draws

- Scene-block bootstrap: 1000 replicates, seed `20260826`; resample complete scenes, never individual adjacent rows.
- Save 2.5%, 50% and 97.5% intervals for fitted scalar parameters and key model quantiles.
- Generate 4096 deterministic QA draws per cell with seed `20260827`; they are diagnostics, not final simulator data.
- For cells with fewer than two scenes, cross-scene validation is `NOT_ESTIMABLE_SPARSE_GROUP`, not PASS.

---

### Task 1: Freeze configuration and source/coverage contract

**Files:**
- Create: `configs/channel_modeling/environment_elevation_path_distribution_v1.json`
- Create: `scripts/analysis/channel_modeling/__init__.py`
- Create: `scripts/analysis/channel_modeling/path_distribution_core.py`
- Create: `scripts/analysis/channel_modeling/tests/test_path_distribution_core.py`

**Interfaces:**
- `load_frozen_config(path: Path) -> FitConfig`
- `load_path_observations(project_root: Path, config: FitConfig) -> tuple[list[PathObservation], SourceAudit]`
- `build_cell_coverage(observations: Sequence[PathObservation]) -> list[CellCoverage]`

- [ ] **Step 1: Write failing source and coverage tests.**

```python
def test_source_contract_and_coverage(project_root, frozen_config):
    rows, audit = load_path_observations(project_root, frozen_config)
    coverage = {(x.environment, x.elevation_band): x.path_count
                for x in build_cell_coverage(rows)}
    assert audit.source_sha256 == "2a44913d1c06f78d2748428b1d72f1b4712a6b5d3f33fc598a14fe17a3e3414a"
    assert (audit.environment_ready_count, audit.elevation_ready_count,
            audit.elevation_excluded_count) == (100, 84, 16)
    assert len(coverage) == 12
    assert coverage[("Urban", "LOW")] == 0
    assert coverage[("Highway/Open", "LOW")] == 0
    assert sum(coverage.values()) == 84
```

Also reject a changed source hash, Stage2/3 row, `is_multipath=0`, invalid environment/bin, non-finite parameter, or elevation-ready row with `geometry_join_valid=0`.

- [ ] **Step 2: Run RED test.**

Run `D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe -m pytest scripts\analysis\channel_modeling\tests\test_path_distribution_core.py -q`.

Expected: missing config/interfaces.

- [ ] **Step 3: Create the frozen config.**

Record model ID, source path/hash, cells/bins, family order, tie tolerance, prior weights, quantile count, copula constants, seeds/counts, output namespace, execution prohibitions and `gold_labels_used_for_selection=false`.

- [ ] **Step 4: Implement strict loading and cell accounting.**

Retain the 16 excluded-elevation rows with `elevation_band=None` for parent fits. Validate Stage4 semantics before accepting any row.

- [ ] **Step 5: Re-run tests; expect GREEN.**

- [ ] **Step 6: Commit only Task 1 files after auditing unrelated dirty changes.**

Run `git add configs/channel_modeling/environment_elevation_path_distribution_v1.json scripts/analysis/channel_modeling/__init__.py scripts/analysis/channel_modeling/path_distribution_core.py scripts/analysis/channel_modeling/tests/test_path_distribution_core.py` and then `git commit -m "feat: freeze environment elevation path inputs"`.

### Task 2: Implement unit transforms and inverse sampling

**Files:**
- Modify: `scripts/analysis/channel_modeling/path_distribution_core.py`
- Modify: `scripts/analysis/channel_modeling/tests/test_path_distribution_core.py`

**Interfaces:**
- `to_model_vector(observation: PathObservation) -> ModelVector`
- `relative_power_db_to_amplitude(power_db: NDArray) -> NDArray`
- `model_draw_to_output(delay_ns: float, doppler_hz: float, power_db: float) -> PathDraw`

- [ ] **Step 1: Write failing tests.**

```python
def test_units_and_amplitude_conversion():
    v = to_model_vector(example_observation(excess_delay_s=1e-7,
                                            relative_doppler_hz=-12.5,
                                            relative_power_db=-6.020599913279624))
    assert v.relative_delay_ns == pytest.approx(100.0, abs=1e-12)
    assert v.relative_doppler_hz == -12.5
    assert relative_power_db_to_amplitude(np.array([-6.020599913279624]))[0] == pytest.approx(0.5)
```

Also prove positive dB remains amplitude >1, Doppler sign is preserved, and non-positive NLOS delay fails closed rather than receiving an epsilon shift.

- [ ] **Step 2: Run focused test; expect RED.**
- [ ] **Step 3: Implement exact transforms.** Keep delay ns, Doppler Hz and power dB inside fitting; convert to linear amplitude only on output. Do not add main-path or phase fields.
- [ ] **Step 4: Re-run focused test; expect GREEN.**
- [ ] **Step 5: Commit Task 2 files only.**

### Task 3: Select one global marginal family per parameter

**Files:**
- Modify: `scripts/analysis/channel_modeling/path_distribution_core.py`
- Modify: `scripts/analysis/channel_modeling/tests/test_path_distribution_core.py`

**Interfaces:**
- `fit_family(values: NDArray, weights: NDArray, family: str) -> FamilyFit`
- `score_family_by_scene(observations: Sequence[ModelVector], parameter: str, family: str) -> FamilyScore`
- `select_global_family(observations: Sequence[ModelVector], parameter: str, candidates: Sequence[str]) -> FamilySelection`
- `cdf(fit: FamilyFit, values: NDArray) -> NDArray`
- `ppf(fit: FamilyFit, probabilities: NDArray) -> NDArray`

- [ ] **Step 1: Write failing distribution tests.** Use deterministic lognormal/Gamma/Student-t/Laplace fixtures; assert finite weighted fits, fixed-zero location for delay, Student-t df in `[2.1,100]`, positive scales, CDF/PPF agreement within `1e-8`, and deterministic ties.
- [ ] **Step 2: Write a grouped-validation test.**

```python
def test_selection_holds_out_complete_scenes():
    s = select_global_family(grouped_fixture(), "relative_doppler_hz",
                             ("student_t", "normal", "laplace"))
    assert s.held_out_groups == {"scene_a", "scene_b", "scene_c"}
    assert s.row_random_split_used is False
```

- [ ] **Step 3: Run tests; expect RED.**
- [ ] **Step 4: Implement bounded deterministic MLE and leave-one-scene-out scoring.** Record every fold and invalidate rather than omit a failed fold.
- [ ] **Step 5: Re-run tests; expect GREEN.**
- [ ] **Step 6: Commit Task 3 files only.**

### Task 4: Fit hierarchical environment and cell marginals

**Files:**
- Modify: `scripts/analysis/channel_modeling/path_distribution_core.py`
- Modify: `scripts/analysis/channel_modeling/tests/test_path_distribution_core.py`

**Interfaces:**
- `parent_quantiles(fit: FamilyFit, count: int) -> NDArray`
- `fit_hierarchical_marginals(observations: Sequence[ModelVector], selections: Mapping[str, FamilySelection], config: FitConfig) -> HierarchicalMarginalResult`
- `classify_support(path_count: int, scene_count: int) -> str`

- [ ] **Step 1: Write failing deterministic-prior tests.** Assert 64 parent quantiles carry total weight 8, repeated calls are identical, parent hierarchy is global→environment→cell, and excluded-elevation rows never enter cell likelihoods.
- [ ] **Step 2: Write sparse/empty-cell tests.**

```python
def test_empty_cell_is_exact_environment_parent():
    result = fit_hierarchical_marginals(sparse_fixture(), selections(), config())
    cell = result.cell("Urban", "LOW", "relative_delay_ns")
    parent = result.environment("Urban", "relative_delay_ns")
    assert cell.parameters == parent.parameters
    assert cell.local_likelihood_row_count == 0
    assert cell.support_status == "PRIOR_ONLY"
    assert cell.parameter_source == "environment_parent_only"
```

Verify `n=1/2` prior-dominant, `n=3..9` sparse partial pooling, and data-supported status requires both `n>=10` and at least two scenes.

- [ ] **Step 3: Run tests; expect RED.**
- [ ] **Step 4: Implement weighted parent/environment/cell fits.** Produce exactly 36 marginal records: 12 cells × 3 parameters, each with family, parameters, local counts, parent IDs, weights, likelihood and support status.
- [ ] **Step 5: Re-run tests; expect GREEN.**
- [ ] **Step 6: Commit Task 4 files only.**

### Task 5: Add environment-level Gaussian copulas

**Files:**
- Modify: `scripts/analysis/channel_modeling/path_distribution_core.py`
- Modify: `scripts/analysis/channel_modeling/tests/test_path_distribution_core.py`

**Interfaces:**
- `fit_global_copula(vectors, marginals, config) -> CopulaModel`
- `fit_environment_copulas(vectors, global_model, config) -> dict[str, CopulaModel]`
- `nearest_correlation(matrix: NDArray, eigenvalue_floor: float) -> tuple[NDArray, float]`
- `sample_cell(cell: CellKey, n: int, seed: int, marginals, copulas) -> NDArray`

- [ ] **Step 1: Write failing PSD/shrinkage/determinism tests.** Require symmetry, unit diagonal, minimum eigenvalue `>=1e-6`, shrink weight `n/(n+10)`, and identical seeded samples.
- [ ] **Step 2: Write support tests.** For all 12 cells and 4096 draws require delay >0, finite signed Doppler/power, positive linear amplitude, environment-copula reference and no cell covariance estimate.
- [ ] **Step 3: Run tests; expect RED.**
- [ ] **Step 4: Implement rank transform, shrinkage, PSD correction and inverse marginal sampling.** Persist raw/final matrices, weight and correction norm.
- [ ] **Step 5: Re-run tests; expect GREEN.**
- [ ] **Step 6: Commit Task 5 files only.**

### Task 6: Add scene-block uncertainty and diagnostics

**Files:**
- Modify: `scripts/analysis/channel_modeling/path_distribution_core.py`
- Modify: `scripts/analysis/channel_modeling/tests/test_path_distribution_core.py`

**Interfaces:**
- `scene_block_bootstrap(observations, config) -> BootstrapResult`
- `build_predictive_diagnostics(model, observations, config) -> list[DiagnosticRecord]`

- [ ] **Step 1: Write failing grouped-bootstrap tests.** Assert full scene blocks, seed 20260826, exactly 1000 success/failure receipts, and no silent replacement of failed replicates.
- [ ] **Step 2: Write failing predictive tests.** Analytic and synthetic marginal quantiles must agree within fixed Monte Carlo tolerance; 4096-draw correlation must match assigned copula within absolute 0.05; every cell, including prior-only cells, must have diagnostics.
- [ ] **Step 3: Run tests; expect RED.**
- [ ] **Step 4: Implement intervals and diagnostics.** Save 2.5/50/97.5% intervals; mark sparse cross-scene validation `NOT_ESTIMABLE_SPARSE_GROUP`; mark prior-only uncertainty as inherited.
- [ ] **Step 5: Re-run tests; expect GREEN.**
- [ ] **Step 6: Commit Task 6 files only.**

### Task 7: Implement new-only builder and immutable outputs

**Files:**
- Create: `scripts/analysis/channel_modeling/build_environment_elevation_path_model.py`
- Create: `scripts/analysis/channel_modeling/tests/test_build_environment_elevation_path_model.py`

**Interfaces:**
- `build_model(project_root: Path, config_path: Path, output_dir: Path) -> BuildReceipt`
- CLI: `--project-root`, `--config`, `--output`, optional `--validate-only`

- [ ] **Step 1: Write failing namespace tests.** Reject existing output without modification, output under `scenes`/`sage_results`, changed config/source hash, and any preflight failure before directory creation.
- [ ] **Step 2: Write failing artifact-schema tests.** Require:

```text
source_path_audit.csv
cell_coverage.csv
marginal_family_selection.csv
global_environment_marginals.csv
cell_distribution_parameters.csv
environment_copula_parameters.csv
cell_model_index.csv
bootstrap_uncertainty.csv
fit_diagnostics.csv
sampling_contract.json
model_manifest.json
model_report.md
build_receipt.json
```

- [ ] **Step 3: Run tests; expect RED.**
- [ ] **Step 4: Implement atomic new-only publication.** Record config/source/script/backend hashes, Python/package/backend receipt, counts, family scores, hierarchy, support, uncertainty and all output hashes. Execution flags must all be false for raw IQ, MATLAB, SAGE, batch and final generator.
- [ ] **Step 5: Freeze `sampling_contract.json`.** It must state cell key, three output quantities/units, `/20` amplitude conversion, external main path/phase/lock/absolute-power semantics, conditional-IID downstream NLOS assumption and mandatory support-status propagation.
- [ ] **Step 6: Re-run tests; expect GREEN.**
- [ ] **Step 7: Commit Task 7 files only.**

### Task 8: Implement independent model QA

**Files:**
- Create: `scripts/analysis/channel_modeling/audit_environment_elevation_path_model.py`
- Create: `scripts/analysis/channel_modeling/tests/test_audit_environment_elevation_path_model.py`

**Interfaces:**
- `audit_model(project_root: Path, config_path: Path, model_dir: Path) -> AuditResult`
- CLI: `--project-root`, `--config`, `--model-dir`

- [ ] **Step 1: Write failing tamper tests.** Independently reject a changed source hash, Stage3 row, elevation assignment to one of the 16 excluded rows, `/10` amplitude conversion, absolute-value Doppler, changed prior-only status, non-PSD copula and altered output hash.
- [ ] **Step 2: Run tests; expect RED.**
- [ ] **Step 3: Implement independent auditing.** Recompute counts, transforms, cell sums, PSD, distribution normalization and hashes without calling builder fit functions. Verify 100/84/16, 12 cells, 36 marginals, two exact prior-only cells and protected pipeline hash.
- [ ] **Step 4: Emit fixed gates.**

```text
BUILD_OUTPUT_COMPLETE = PASS/FAIL
SOURCE_AND_LABEL_GATE = PASS/FAIL
CELL_COVERAGE_GATE = PASS/FAIL
MARGINAL_FIT_GATE = PASS/FAIL
COPULA_GATE = PASS/FAIL
GROUPED_VALIDATION_GATE = PASS_WITH_LIMITATIONS/FAIL
MODEL_QA = PASS_WITH_LIMITATIONS/FAIL
READY_FOR_DARKROOM_GENERATOR_INTEGRATION = YES/NO
```

`PASS_WITH_LIMITATIONS` is expected when hard checks pass but sparse/prior-only cells remain. Never call the model universally validated.

- [ ] **Step 5: Re-run tests; expect GREEN.**
- [ ] **Step 6: Commit Task 8 files only.**

### Task 9: Execute the first Python-only fit and QA

**Runtime output:** `dataset_generation_logs/channel_modeling/environment_elevation_path_distribution_v1_20260826_r1/`

- [ ] **Step 1: Run compilation and focused tests.**

```powershell
D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe -m py_compile scripts\analysis\channel_modeling\path_distribution_core.py scripts\analysis\channel_modeling\build_environment_elevation_path_model.py scripts\analysis\channel_modeling\audit_environment_elevation_path_model.py
D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe -m pytest scripts\analysis\channel_modeling\tests -q
```

- [ ] **Step 2: Run `--validate-only`.** It must report source/config hashes, 100/84/16, the 12-cell matrix, backend receipt, target absence and no-execution flags without creating output.
- [ ] **Step 3: Execute exactly once.**

```powershell
D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe scripts\analysis\channel_modeling\build_environment_elevation_path_model.py --project-root E:\GNSS_Multipath_Project --config E:\GNSS_Multipath_Project\configs\channel_modeling\environment_elevation_path_distribution_v1.json --output E:\GNSS_Multipath_Project\dataset_generation_logs\channel_modeling\environment_elevation_path_distribution_v1_20260826_r1
```

This may read only frozen CSV/config inputs. It must not open tracking MAT, raw IQ or Stage source files directly.

- [ ] **Step 4: Run independent QA.**

```powershell
D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe scripts\analysis\channel_modeling\audit_environment_elevation_path_model.py --project-root E:\GNSS_Multipath_Project --config E:\GNSS_Multipath_Project\configs\channel_modeling\environment_elevation_path_distribution_v1.json --model-dir E:\GNSS_Multipath_Project\dataset_generation_logs\channel_modeling\environment_elevation_path_distribution_v1_20260826_r1
```

- [ ] **Step 5: Apply the integration gate.** Set readiness YES only if all source/unit/hash gates pass; all 12 cells and 36 marginals exist; the two LOW empty cells are exactly prior-only; support is not overstated; fits normalize; copulas are PSD/deterministic; QA draws are valid; grouped limitations are explicit; and no old artifact changed.

If any hard gate fails, preserve r1 as an immutable failed experiment and stop. Changed scientific rules require v2/new namespace; do not tune r1 in place.

### Task 10: Report and synchronize status after real QA

**Files:**
- Create after QA only: `docs/ENVIRONMENT_ELEVATION_PATH_DISTRIBUTION_MODEL_V1_REPORT.md`
- Modify after QA only: `docs/GNSS_SAGE_ENGINEERING_HANDOFF_CURRENT.md`
- Modify after QA only: `docs/GNSS_SAGE_PAPER_HANDOFF_CURRENT.md`

- [ ] **Step 1: Write the result report from immutable outputs.** Include source hashes, selected families, all cell support statuses, parent/cell lineage, copula scope, uncertainty, grouped validation, hashes and limitations. Never call prior-only cells empirically validated.
- [ ] **Step 2: Update Engineering Handoff.** Record source/config/output hashes, tests, QA, no-execution flags and integration readiness; keep the lock model separate.
- [ ] **Step 3: Update Paper Handoff with bounded language only.** If QA passes, use `PATH_DISTRIBUTION_MODEL = COMPLETED_WITH_SPARSE_PRIOR_CELLS`, not “complete physical channel model.” Preserve main-gain, phase, lock mapping, path-count and absolute-power limitations.
- [ ] **Step 4: Leave `PAPER_WORKSPACE_INDEX.md` unchanged unless paper asset structure changes.**
- [ ] **Step 5: Run final verification.**

```powershell
git diff --check -- configs/channel_modeling scripts/analysis/channel_modeling docs/ENVIRONMENT_ELEVATION_PATH_DISTRIBUTION_MODEL_V1_REPORT.md docs/GNSS_SAGE_ENGINEERING_HANDOFF_CURRENT.md docs/GNSS_SAGE_PAPER_HANDOFF_CURRENT.md
D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe -m pytest scripts\analysis\channel_modeling\tests -q
Get-FileHash E:\GNSS_Multipath_Project\scripts\sage_pipeline\run_nav_sage_pipeline.m -Algorithm SHA256
```

Expected protected hash: `BFFC123C97AF77F0A797F417D3866E9A34FEAB7729C5C1575352F53BC3571B9C`.

---

## Explicitly Deferred Follow-On Work

1. Main/reference-path common-gain and C/N0 fade-depth model.
2. Mapping of the completed environment lock-loss model to gain/fade/reacquisition behavior.
3. Fixed path-0 plus NLOS-slot-1–3 millisecond generator.
4. Phase initialization, Doppler-continuous phase and post-reacquisition reset semantics.
5. Absolute RF power calibration and darkroom equipment mapping.
6. Multipath occurrence/path-count or inactive-slot model.
7. 20.46 MHz adaptation.

## Completion Boundary

This plan should produce a QA-passed conditional NLOS path-distribution layer, not the final darkroom table. A later Commander decision must authorize composition of:

```text
environment × elevation NLOS distribution
  + main/common gain model
  + environment lock-loss entry/duration model
  + phase assumption
  + fixed four-path output contract
  -> millisecond darkroom parameter generator
```

## Self-Review Checklist

- [ ] Source hash, Stage4-only rule, 100/84/16 accounting and 12-cell matrix are frozen.
- [ ] Every cell has one joint model; empty cells remain visibly `PRIOR_ONLY`.
- [ ] Delay/Doppler/amplitude units match the requested table.
- [ ] Family selection and validation are scene-grouped, not row-random.
- [ ] Partial pooling is deterministic and records parent provenance.
- [ ] Dependence is environment-level; no unsupported cell covariance is invented.
- [ ] Phase, main path, path count, lock depth and absolute power remain out of scope.
- [ ] Output is new-only and hashes all inputs/outputs.
- [ ] Independent QA detects semantic drift and tampering.
- [ ] Handoffs change only after real fit and QA.

