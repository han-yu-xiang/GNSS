# Environment--Elevation Partially Pooled 3D GMM Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and independently validate one partially pooled three-dimensional GMM for excess delay, absolute relative Doppler magnitude, and relative power, with Urban/Mountain-Valley and LOW/MID/HIGH conditional outputs and review visualizations.

**Architecture:** Read the author-approved v2 518-row primary population without altering it, construct a 487-row elevation-conditioned feature layer plus 31 environment-parent-only rows, fit a weighted hierarchical conditional GMM with shared component covariances, and select `K` and pooling strength by scene-grouped validation. All code, models, QA, figures, and tables remain in a new v3 isolated namespace; the formal manuscript and canonical artifacts remain unchanged.

**Tech Stack:** Python 3.12, NumPy, SciPy, Matplotlib, CSV/JSON/Markdown, `unittest`, deterministic weighted EM, scene-block bootstrap.

**Spec:** `docs/vtc2027_spring/supplemental_data_outputs/urban_mountain_stage3_elevation_model_review_v3_conditional_gmm/review/PARTIALLY_POOLED_3D_GMM_DESIGN.md`

## Global Constraints

- Project root is `E:\GNSS_Multipath_Project`.
- New output root is `docs/vtc2027_spring/supplemental_data_outputs/urban_mountain_stage3_elevation_model_review_v3_conditional_gmm/`.
- Read-only source population is `docs/vtc2027_spring/supplemental_data_outputs/urban_mountain_stage3_elevation_model_review_v2_doppler_audit/population/population_primary_admitted.csv`.
- Do not modify v1, v2, `scenes/`, `dataset/`, production logs, formal manuscript files, Evidence Matrix, figures, tables, or handoffs.
- Use only Urban and Mountain/Valley and the existing LOW/MID/HIGH labels.
- Preserve 518 total rows, 487 elevation-ready rows, 31 missing-elevation rows, 236 tracks, 36 runs, 9 scenes, and 18 PRNs.
- Use `track_weight_recomputed_primary`; verify each track sums to one.
- Use absolute relative Doppler magnitude as the primary feature, but preserve signed Doppler and run the signed sensitivity gate.
- Do not interpret a GMM component as a reflector class or physical propagation mechanism.
- Do not call Stage3 rows confirmed multipath paths in paper-facing text.
- Raw IQ read=`NO`; MATLAB=`NO`; SAGE=`NO`; batch=`NO`; Stage4 source=`NO`.
- No git branch, worktree, commit, push, deletion, overwrite, or manuscript synchronization is authorized.
- Replace commit checkpoints with SHA-256 inventory checkpoints because the author has not requested git operations.

## Planned File Structure

```text
urban_mountain_stage3_elevation_model_review_v3_conditional_gmm/
├── README.md
├── review/
│   ├── PARTIALLY_POOLED_3D_GMM_DESIGN.md
│   └── PARTIALLY_POOLED_3D_GMM_IMPLEMENTATION_PLAN.md
├── scripts/
│   ├── build_source_inventory.py
│   ├── audit_doppler_symmetry.py
│   ├── build_gmm_feature_population.py
│   ├── conditional_gmm_core.py
│   ├── fit_conditional_gmm_candidates.py
│   ├── audit_conditional_gmm.py
│   └── generate_conditional_gmm_figures.py
├── tests/
│   ├── test_source_inventory.py
│   ├── test_doppler_symmetry.py
│   ├── test_gmm_feature_population.py
│   ├── test_conditional_gmm_core.py
│   ├── test_conditional_gmm_selection.py
│   ├── test_conditional_gmm_qa.py
│   └── test_conditional_gmm_figures.py
├── provenance/
│   └── source_inventory.json
├── diagnostics/
│   ├── doppler_symmetry_by_scope.csv
│   ├── doppler_symmetry_scene_bootstrap.csv
│   └── doppler_transform_decision.json
├── population/
│   ├── gmm_feature_population.csv
│   └── gmm_cell_support.csv
├── model/
│   ├── candidate_scores.csv
│   ├── scene_loso_scores.csv
│   ├── scene_bootstrap_model_comparison.csv
│   ├── selected_conditional_gmm.json
│   ├── cell_component_parameters.csv
│   ├── cell_model_summary.csv
│   ├── signed_doppler_sensitivity.csv
│   └── review_model_draws.csv
├── figures/
│   ├── conditional_joint_environment_elevation.pdf
│   ├── conditional_joint_environment_elevation.png
│   ├── conditional_joint_corner_diagnostics.pdf
│   ├── conditional_gmm_component_weights.pdf
│   └── conditional_gmm_component_weights.png
├── tables/
│   ├── conditional_gmm_selection_summary.csv
│   ├── conditional_gmm_cell_summary.csv
│   └── conditional_gmm_cell_summary.tex
└── qa/
    ├── model_build_manifest.json
    ├── model_build_report.md
    ├── independent_qa_result.json
    ├── independent_qa_report.md
    └── output_manifest.json
```

---

### Task 1: Freeze source inventory and namespace policy

**Files:**
- Create: `...review_v3_conditional_gmm/README.md`
- Create: `...review_v3_conditional_gmm/scripts/build_source_inventory.py`
- Create: `...review_v3_conditional_gmm/provenance/source_inventory.json`
- Test: `...review_v3_conditional_gmm/tests/test_source_inventory.py`

**Interfaces:**
- Consumes: v2 primary population, population manifest, population independent-QA result, Doppler provenance result, v2 selected-model table, and v2 joint-model result.
- Produces: `source_inventory.json` entries with `path`, `role`, `size_bytes`, `sha256`, and `read_only=true`.

- [ ] **Step 1: Write the namespace and source-hash test**

```python
def test_source_inventory_protects_v2_and_formal_assets(self):
    inventory = load_json(ROOT / "provenance/source_inventory.json")
    self.assertEqual(inventory["execution_policy"]["raw_iq_read"], False)
    self.assertEqual(inventory["execution_policy"]["stage4_used"], False)
    self.assertEqual(inventory["execution_policy"]["formal_manuscript_modified"], False)
    self.assertTrue(all(item["read_only"] for item in inventory["sources"]))
```

- [ ] **Step 2: Run the test and verify the missing-inventory failure**

Run:

```powershell
python -m unittest discover "docs\vtc2027_spring\supplemental_data_outputs\urban_mountain_stage3_elevation_model_review_v3_conditional_gmm\tests" -p "test_source_inventory.py" -v
```

Expected: FAIL because `source_inventory.json` does not yet exist.

- [ ] **Step 3: Implement source hashing and output guards**

Create inventory records for these exact inputs:

```text
v2/population/population_primary_admitted.csv
v2/qa/population_build_manifest.json
v2/qa/population_independent_qa_result.json
v2/qa/doppler_provenance_result.json
v2/model/selected_model_by_parameter.csv
v2/model/joint_dependence_models.csv
v2/qa/joint_model_build_result.json
```

Reject any resolved output under `scenes/`, `dataset/`, `dataset_generation_logs/`, `manuscript/latex/`, v1, or v2.

- [ ] **Step 4: Run the namespace test**

Expected: PASS and seven immutable source records.

- [ ] **Step 5: Record the Task-1 SHA checkpoint**

Record README, inventory, script, and test hashes in `qa/output_manifest.json`. Do not commit.

---

### Task 2: Audit signed-Doppler symmetry and freeze the magnitude transform

**Files:**
- Create: `scripts/audit_doppler_symmetry.py`
- Create: `diagnostics/doppler_symmetry_by_scope.csv`
- Create: `diagnostics/doppler_symmetry_scene_bootstrap.csv`
- Create: `diagnostics/doppler_transform_decision.json`
- Test: `tests/test_doppler_symmetry.py`

**Interfaces:**
- Consumes: v2 primary population.
- Produces: `weighted_mirror_distance(values, weights) -> float`, scope-level sign diagnostics, and a fixed primary transform decision.

- [ ] **Step 1: Write primitive tests**

```python
def test_mirror_distance_is_zero_for_symmetric_atoms(self):
    values = np.asarray([-2.0, -1.0, 1.0, 2.0])
    weights = np.ones(4)
    self.assertAlmostEqual(weighted_mirror_distance(values, weights), 0.0)

def test_absolute_transform_folds_sign_without_changing_units(self):
    values = np.asarray([-50.0, 0.0, 100.0])
    np.testing.assert_allclose(absolute_doppler(values), [50.0, 0.0, 100.0])
```

- [ ] **Step 2: Run the primitive tests and verify failure**

Expected: FAIL because the functions do not exist.

- [ ] **Step 3: Implement scope diagnostics**

For global, two environments, and six environment--elevation cells, calculate:

```text
observation_count, track_count, run_count, scene_count,
sum_weights, Kish effective sample size,
weighted positive/negative/zero mass,
weighted mean, median, q025, q25, q75, q975,
weighted mirror-CDF distance,
four-mode count and coarse-grid-match count.
```

- [ ] **Step 4: Implement 1000 scene-block bootstrap replicates**

Use seed `2026083103`. Resample scenes within each environment; never resample rows independently.

- [ ] **Step 5: Freeze the transform decision**

Write:

```json
{
  "primary_model_variable": "absolute_relative_doppler_magnitude_hz",
  "source_field_preserved": "doppler_offset_hz",
  "transform": "log1p(abs(doppler_offset_hz)/1Hz)",
  "physical_symmetry_claim": false,
  "signed_sensitivity_required": true,
  "stop_if_signed_sensitivity_stably_better": true
}
```

- [ ] **Step 6: Verify counts and scientific wording**

Expected: 518 total, 487 elevation-ready, no excluded rows, and no statement that the four Doppler modes are physical regimes.

- [ ] **Step 7: Record the Task-2 SHA checkpoint**

Add hashes and the bootstrap seed to `qa/output_manifest.json`.

---

### Task 3: Build the transformed feature population

**Files:**
- Create: `scripts/build_gmm_feature_population.py`
- Create: `population/gmm_feature_population.csv`
- Create: `population/gmm_cell_support.csv`
- Test: `tests/test_gmm_feature_population.py`

**Interfaces:**
- Consumes: v2 primary rows and the Doppler transform decision.
- Produces: `transform_row(raw: Mapping[str,str]) -> dict[str,Any]` and a feature CSV retaining source values and transformed values.

- [ ] **Step 1: Write count, transform, and weight tests**

```python
def test_feature_population_denominators(self):
    rows = read_csv(ROOT / "population/gmm_feature_population.csv")
    self.assertEqual(len(rows), 518)
    self.assertEqual(sum(r["cell_ready"] == "1" for r in rows), 487)
    self.assertEqual(sum(r["cell_ready"] == "0" for r in rows), 31)

def test_track_weights_sum_to_one(self):
    for total in weight_sums_by_track(rows).values():
        self.assertAlmostEqual(total, 1.0, places=12)
```

- [ ] **Step 2: Run tests and verify missing-output failure**

- [ ] **Step 3: Implement feature construction**

Retain these source fields unchanged:

```text
stage3_path_id, track_id, run_id, scene_id, prn,
environment_class, elevation_deg, elevation_band, elevation_ready,
excess_delay_samples, doppler_offset_hz, relative_power_db,
track_weight_recomputed_primary, doppler_provenance_class.
```

Add:

```text
absolute_doppler_hz,
log_excess_delay,
log1p_absolute_doppler,
cell_ready,
parent_scope_role.
```

- [ ] **Step 4: Assert the six cell counts**

Expected observation counts:

```text
Urban LOW=18, MID=169, HIGH=129
Mountain/Valley LOW=22, MID=117, HIGH=32
```

- [ ] **Step 5: Verify support and missing-elevation policy**

The 31 missing-elevation rows must have `parent_scope_role=ENVIRONMENT_PARENT_ONLY` and blank cell ID. No elevation is imputed.

- [ ] **Step 6: Record the Task-3 SHA checkpoint**

---

### Task 4: Implement the weighted partially pooled GMM core

**Files:**
- Create: `scripts/conditional_gmm_core.py`
- Test: `tests/test_conditional_gmm_core.py`

**Interfaces:**
- Produces:

```python
@dataclass(frozen=True)
class ConditionalGMMConfig:
    component_count: int
    pooling_kappa: float
    max_iterations: int = 500
    tolerance: float = 1e-7
    covariance_floor: float = 1e-5
    weight_floor: float = 1e-6
    restart_count: int = 10
    seed: int = 2026083104

@dataclass
class ConditionalGMM:
    config: ConditionalGMMConfig
    transform_center: np.ndarray
    transform_scale: np.ndarray
    global_weights: np.ndarray
    global_means: np.ndarray
    environment_weights: dict[str, np.ndarray]
    environment_means: dict[str, np.ndarray]
    cell_weights: dict[str, np.ndarray]
    shared_covariances: np.ndarray
    log_likelihood_history: list[float]

def fit_conditional_gmm(rows: Sequence[Mapping[str, Any]], config: ConditionalGMMConfig) -> ConditionalGMM: ...
def log_predictive_density(model: ConditionalGMM, rows: Sequence[Mapping[str, Any]]) -> np.ndarray: ...
def sample_conditional(model: ConditionalGMM, environment: str, elevation_band: str | None, count: int, seed: int) -> np.ndarray: ...
```

- [ ] **Step 1: Write synthetic recovery tests**

```python
def test_two_component_model_recovers_separated_clusters(self):
    rows = make_synthetic_conditional_rows(seed=7, components=2)
    model = fit_conditional_gmm(rows, ConditionalGMMConfig(2, 8.0))
    self.assertEqual(model.global_weights.shape, (2,))
    self.assertTrue(np.all(np.linalg.eigvalsh(model.shared_covariances) >= 1e-5 - 1e-10))
    self.assertLess(model.global_means[0, 2], model.global_means[1, 2])
```

- [ ] **Step 2: Write pooling tests**

```python
def test_sparse_cell_moves_toward_environment_parent_as_kappa_increases(self):
    weak = fit_conditional_gmm(rows, ConditionalGMMConfig(2, 4.0))
    strong = fit_conditional_gmm(rows, ConditionalGMMConfig(2, 32.0))
    self.assertLess(
        np.linalg.norm(strong.cell_weights["Urban__LOW"] - strong.environment_weights["Urban"]),
        np.linalg.norm(weak.cell_weights["Urban__LOW"] - weak.environment_weights["Urban"]),
    )
```

- [ ] **Step 3: Write deterministic and monotonic-likelihood tests**

Two runs with the same seed must match within `1e-12`; the accepted EM history must not decrease by more than `1e-8`.

- [ ] **Step 4: Run tests and verify failure**

- [ ] **Step 5: Implement weighted initialization and E-step**

Use deterministic weighted k-means++ initialization in standardized three-dimensional space. Elevation-ready rows use cell weights; missing-elevation rows use environment weights.

- [ ] **Step 6: Implement the partially pooled M-step**

Apply track weights to responsibilities. Shrink environment weights and means to the global parent and cell weights to the environment parent using the configured track-equivalent `kappa`. Share each component covariance across all environments and cells.

- [ ] **Step 7: Implement numerical safeguards and label ordering**

Floor eigenvalues at `1e-5`, floor weights at `1e-6`, normalize, reject non-finite candidates, and order labels by power mean, Doppler-magnitude mean, then delay mean.

- [ ] **Step 8: Run the core tests**

Expected: all synthetic, pooling, determinism, PSD, and sampling tests PASS.

- [ ] **Step 9: Record the Task-4 SHA checkpoint**

---

### Task 5: Fit candidates and perform grouped model selection

**Files:**
- Create: `scripts/fit_conditional_gmm_candidates.py`
- Create: all `model/*.csv` and `model/selected_conditional_gmm.json`
- Test: `tests/test_conditional_gmm_selection.py`

**Interfaces:**
- Consumes: feature population and `conditional_gmm_core.py`.
- Produces: 12 candidate summaries, nine-scene LOSO rows per candidate, selected model, bootstrap comparison, signed sensitivity, and deterministic model draws.

- [ ] **Step 1: Write scene-split leakage tests**

```python
def test_scene_loso_never_leaks_rows(self):
    for fold in build_scene_folds(rows):
        self.assertTrue(set(fold.train_scene_ids).isdisjoint(fold.test_scene_ids))
        self.assertEqual(len(fold.test_scene_ids), 1)
```

- [ ] **Step 2: Write candidate-grid and selection tests**

Require exactly 12 `(K,kappa)` combinations and reject a candidate if any scene fold fails.

- [ ] **Step 3: Implement training-fold transforms**

Fit weighted center/scale only on training scenes. Apply those frozen values to the held-out scene. Never standardize using all 518 rows during LOSO.

- [ ] **Step 4: Fit the candidate grid**

Use:

```text
K = 1, 2, 3
kappa = 4, 8, 16, 32
10 deterministic restarts per candidate and fold
```

Store held-out weighted NLPD, three-dimensional energy score, convergence status, component effective mass, and covariance minimum eigenvalue.

- [ ] **Step 5: Implement selection and complexity preference**

Choose the lowest valid scene-grouped NLPD. If a larger `K` does not have a paired scene-block 95% interval entirely below zero versus the smaller valid `K`, retain the smaller `K`.

- [ ] **Step 6: Run 1000 scene-block bootstrap comparisons**

Use seed `2026083105`. Record all successful replicates and fail if fewer than 1000 complete.

- [ ] **Step 7: Compare common baselines**

Evaluate:

```text
conditional K=1 Gaussian
existing v2 marginal-plus-copula model mapped to absolute Doppler
selected conditional GMM
```

Use the same deterministic energy-score draws so all three models are comparable.

- [ ] **Step 8: Run the signed-Doppler sensitivity gate**

Fit the selected `(K,kappa)` architecture using signed Doppler. If signed minus absolute energy-score loss has a paired 95% interval entirely below zero, write `STOP_AUTHOR_REVIEW_SIGN_INFORMATION_MATERIAL`; otherwise retain absolute Doppler as the primary model variable.

- [ ] **Step 9: Fit the selected full-population review model**

Create global parent, two environment parents, and six cell conditional records. Generate exactly 4096 review draws per cell with seed `2026083106`, for 24,576 draw rows.

- [ ] **Step 10: Run selection tests and record Task-5 hashes**

Expected: deterministic selected JSON, 12 candidate rows, complete nine-scene fold coverage, 1000 bootstrap replicates, and no formal-paper write.

---

### Task 6: Perform independent QA

**Files:**
- Create: `scripts/audit_conditional_gmm.py`
- Create: `qa/independent_qa_result.json`
- Create: `qa/independent_qa_report.md`
- Create: `qa/model_build_manifest.json`
- Test: `tests/test_conditional_gmm_qa.py`

**Interfaces:**
- Consumes: immutable source inventory, population, diagnostics, model outputs, and selected model.
- Produces: independent `PASS`, `PASS_WITH_LIMITATIONS`, or `FAIL` and exact failure reasons.

- [ ] **Step 1: Write independent QA tests**

```python
def test_selected_model_has_six_conditioned_cells(self):
    result = load_json(ROOT / "qa/independent_qa_result.json")
    self.assertEqual(result["counts"]["conditioned_cells"], 6)
    self.assertEqual(result["counts"]["primary_rows"], 518)
    self.assertEqual(result["counts"]["cell_ready_rows"], 487)
```

- [ ] **Step 2: Independently verify source and population integrity**

Recompute all hashes, keys, denominators, cell counts, track-weight sums, and missing-elevation rules without importing builder summary functions.

- [ ] **Step 3: Independently verify model mathematics**

Check mixture weights sum to one, covariances are symmetric positive definite, component labels are ordered, likelihoods are finite, selected complexity follows the rule, all nine scene folds exist, and all 1000 bootstrap replicates are complete.

- [ ] **Step 4: Independently verify scientific boundaries**

Fail if any report calls a component a physical reflector class, treats grid peaks as propagation modes, calls Stage3 rows confirmed paths, imputes elevation, or claims a complete stochastic channel model.

- [ ] **Step 5: Assign support status by cell**

Use only:

```text
DATA_SUPPORTED
STRONGLY_PARTIALLY_POOLED
MODEL_INVALID
```

Urban--LOW, Mountain/Valley--LOW, and Mountain/Valley--HIGH cannot be promoted above `STRONGLY_PARTIALLY_POOLED` solely because the fitted curve looks smooth.

- [ ] **Step 6: Run all tests**

Run:

```powershell
python -m unittest discover "docs\vtc2027_spring\supplemental_data_outputs\urban_mountain_stage3_elevation_model_review_v3_conditional_gmm\tests" -p "test_*.py" -v
```

Expected: all tests PASS and independent QA is at least `PASS_WITH_LIMITATIONS`.

- [ ] **Step 7: Stop on QA failure**

Preserve failed artifacts. Do not tune exclusions, change cells, or remove rows to improve the model.

---

### Task 7: Generate author-review figures and tables

**Files:**
- Create: `scripts/generate_conditional_gmm_figures.py`
- Create: all planned `figures/*` and `tables/*`
- Test: `tests/test_conditional_gmm_figures.py`

**Interfaces:**
- Consumes: QA-admitted selected model, feature population, cell support, and deterministic review draws.
- Produces: review figures and compact CSV/LaTeX tables; no manuscript edit.

- [ ] **Step 1: Write figure/table existence and denominator tests**

```python
def test_main_figure_contains_six_cells(self):
    manifest = load_json(ROOT / "qa/output_manifest.json")
    self.assertEqual(manifest["figures"]["conditional_joint_environment_elevation"]["panel_count"], 6)
    self.assertEqual(manifest["figures"]["conditional_joint_environment_elevation"]["cell_ready_rows"], 487)
```

- [ ] **Step 2: Generate the 2-by-3 primary review figure**

Rows: Urban and Mountain/Valley. Columns: LOW, MID, HIGH. Each panel must show:

```text
empirical delay--power points,
selected-model delay--power density contours,
absolute-Doppler magnitude on a shared color scale,
observation/track/scene counts,
support status.
```

- [ ] **Step 3: Generate six corner-plot diagnostic pages**

Each page shows delay--power, delay--absolute-Doppler, and absolute-Doppler--power empirical/model projections plus all three marginals. Mark it `INTERNAL_DIAGNOSTIC`.

- [ ] **Step 4: Generate mixture-weight heatmap**

Use a 2-by-3 cell layout and one color per selected component. Keep component colors consistent across every figure.

- [ ] **Step 5: Generate selection and cell-summary tables**

Report selected `K`, `kappa`, model status, cell support, component weights, transformed-back median/5%/95% values, observation count, track count, and scene count. Do not report a component as a reflector type.

- [ ] **Step 6: Perform visual QA**

Render the PDFs to PNG previews. Check clipped labels, shared color limits, readable counts, consistent units, LOW/MID/HIGH ordering, and absence of CDF panels.

- [ ] **Step 7: Record figure/table hashes and stop at author gate**

Do not copy figures into the formal manuscript. Present the selected model, signed-versus-absolute Doppler decision, main 2-by-3 figure, corner diagnostics, mixture weights, and cell table for author review.

---

## Author Gate and Completion Record

Execution stops after Task 7. The report must include:

```text
SOURCE_POPULATION_ROWS = 518
CELL_READY_ROWS = 487
MISSING_ELEVATION_ROWS = 31
PRIMARY_DOPPLER_VARIABLE = absolute relative Doppler magnitude
SIGNED_DOPPLER_SENSITIVITY_STATUS = RESULT_FROM_TASK_5_SIGN_GATE
SELECTED_COMPONENT_COUNT_K = RESULT_FROM_TASK_5_SELECTION
SELECTED_POOLING_KAPPA = RESULT_FROM_TASK_5_SELECTION
SELECTED_MODEL_VALIDATION_STATUS = RESULT_FROM_TASK_6_INDEPENDENT_QA
GLOBAL_PARENT_ROLE = REGULARIZATION_ONLY
CONDITIONED_CELL_COUNT = 6
STRONGLY_POOLED_CELLS = Urban-LOW; Mountain/Valley-LOW; Mountain/Valley-HIGH
PAPER_ADMISSION_RECOMMENDATION = PENDING_AUTHOR_REVIEW

RAW_IQ_READ = NO
MATLAB_EXECUTED = NO
SAGE_EXECUTED = NO
BATCH_EXECUTED = NO
STAGE4_SOURCE_USED = NO
PRODUCTION_ARTIFACT_MODIFIED = NO
FORMAL_MANUSCRIPT_MODIFIED = NO

Handoff impact:
- Engineering handoff update required: NO
- Paper handoff update required: NO until author admits the model

NEXT_DECISION_REQUIRED = AUTHOR REVIEW OF MODEL, SIGN GATE, FIGURES, AND TABLE
```

No manuscript-copy task is included in this plan. After author approval, manuscript reconstruction must receive a separate plan and must begin from a new isolated copy rather than the formal manuscript directory.
