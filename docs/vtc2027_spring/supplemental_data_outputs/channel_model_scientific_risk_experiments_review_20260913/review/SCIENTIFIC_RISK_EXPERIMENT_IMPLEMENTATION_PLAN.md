# Scientific-Risk Supplemental Experiments Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce independently checkable scene-held-out and scene-bootstrap evidence for the current Doppler, relative-power, and power-delay models without changing the manuscript or source population.

**Architecture:** A small pure numerical core will validate the fixed population, fit weighted one-dimensional Gaussian mixtures, and fit weighted straight/connected-line regressions. A runner will execute the frozen comparisons and write CSV/JSON/figures. A separate QA program will recompute denominators and verify folds, weights, finite parameters, bootstrap counts, and hashes.

**Tech Stack:** Python 3.12, NumPy, SciPy, pandas, Matplotlib, unittest.

**Spec:** `review/SCIENTIFIC_RISK_EXPERIMENT_SPEC.md`

## Global Constraints

- Read only the 518-row primary population selected by `primary_population_included == true`.
- Keep all 346 Urban and 172 Mountain/Valley rows; perform no outlier deletion.
- Recompute equal-total track weights after every scene resample.
- Hold out complete `scene_id` groups; never split a scene across training and evaluation.
- Use deterministic seeds recorded in the output manifest.
- Do not run MATLAB, SAGE, raw-IQ processing, or any production pipeline.
- Do not modify any manuscript, handoff, Evidence Matrix, source model, or historical review directory.
- No Git worktree or branch is used because the author explicitly required directory-based isolation.

---

### Task 1: Population and weighting contract

**Files:**
- Create: `tests/test_scientific_risk_core.py`
- Create: `scripts/scientific_risk_core.py`

**Interfaces:**
- `load_primary_population(path: Path) -> pandas.DataFrame`
- `recompute_track_weights(frame: pandas.DataFrame, track_column: str = "track_id") -> pandas.DataFrame`
- Produces a validated frame with numeric parameter columns and `analysis_weight` whose sum is one for every track.

- [ ] **Step 1: Write the failing population tests**

```python
def test_recompute_track_weights_gives_each_track_unit_mass():
    frame = fixture_with_track_sizes_two_and_one()
    weighted = recompute_track_weights(frame)
    assert weighted.groupby("track_id")["analysis_weight"].sum().to_dict() == {"a": 1.0, "b": 1.0}

def test_load_primary_population_rejects_wrong_denominator(tmp_path):
    path = write_population_fixture(tmp_path, primary_rows=3)
    with pytest.raises(ValueError, match="expected 518"):
        load_primary_population(path)
```

- [ ] **Step 2: Run the tests and verify failure because the module does not exist**

Run: `python -m unittest tests.test_scientific_risk_core -v`

- [ ] **Step 3: Implement validation and weight recomputation**

The loader must require the source fields, select the primary flag, enforce the exact total/environment/track/scene counts, convert the three model fields to finite numbers, and call `recompute_track_weights`.

- [ ] **Step 4: Run the tests and verify they pass**

Run: `python -m unittest tests.test_scientific_risk_core -v`

### Task 2: Weighted Gaussian mixtures and scene-held-out comparison

**Files:**
- Modify: `tests/test_scientific_risk_core.py`
- Modify: `scripts/scientific_risk_core.py`

**Interfaces:**
- `fit_weighted_gmm(values, weights, components, seed) -> dict`
- `gmm_logpdf(values, model) -> numpy.ndarray`
- `gmm_cdf(values, model) -> numpy.ndarray`
- `evaluate_gmm_complexity(frame, value_column, seeds) -> tuple[pandas.DataFrame, pandas.DataFrame]`

- [ ] **Step 1: Add failing tests with hand-built two-peak data**

Assert that means are ordered, weights sum to one, all standard deviations are positive, a two-peak fixture is fitted near its two hand-set centers, and fold rows contain disjoint training/held-out scene names.

- [ ] **Step 2: Run the focused tests and verify the missing functions fail**

Run: `python -m unittest tests.test_scientific_risk_core.GaussianMixtureTests -v`

- [ ] **Step 3: Implement deterministic weighted EM and K=1,2,3 LOSO evaluation**

Use weighted-quantile starts plus fixed seeded starts, log-sum-exp responsibilities, a `0.25` unit standard-deviation floor, 500 iterations, ordered component means, and an effective-component-weight floor of five. Calculate weighted NLPD on each untouched scene and apply the one-standard-error complexity rule.

- [ ] **Step 4: Run all Task 1-2 tests**

Run: `python -m unittest tests.test_scientific_risk_core -v`

### Task 3: Leakage-safe power-delay comparison

**Files:**
- Modify: `tests/test_scientific_risk_core.py`
- Modify: `scripts/scientific_risk_core.py`

**Interfaces:**
- `fit_weighted_line(frame) -> dict`
- `fit_connected_lines(frame, breakpoint) -> dict`
- `choose_training_breakpoint(frame, candidates) -> float`
- `evaluate_power_delay_models(frame, candidates) -> tuple[pandas.DataFrame, pandas.DataFrame]`

- [ ] **Step 1: Add failing breakpoint tests**

Use a hand-built connected-line fixture with a 2.0-sample knot. Assert continuity, recovery of the two slopes, and unchanged selected breakpoint when only the held-out scene values are perturbed.

- [ ] **Step 2: Run the focused tests and verify failure**

Run: `python -m unittest tests.test_scientific_risk_core.PowerDelayTests -v`

- [ ] **Step 3: Implement straight-line, fixed-knot, and training-selected-knot fits**

Use weighted least squares. The selected knot minimizes training BIC over `numpy.arange(1.25, 3.251, 0.10)` subject to at least five tracks and five units of weight on each side. Evaluate weighted RMSE and MAE only on the outer held-out scene.

- [ ] **Step 4: Run the complete core test suite**

Run: `python -m unittest tests.test_scientific_risk_core -v`

### Task 4: Scene-block bootstrap and artifact runner

**Files:**
- Modify: `tests/test_scientific_risk_core.py`
- Create: `scripts/run_scientific_risk_experiments.py`

**Interfaces:**
- `scene_bootstrap(frame, fit_kind, replicates, seed) -> pandas.DataFrame`
- Runner outputs `tables/gmm_complexity_summary.csv`, `tables/gmm_loso_folds.csv`, `tables/power_delay_model_summary.csv`, `tables/power_delay_loso_folds.csv`, `tables/scene_bootstrap_intervals.csv`, `model/experiment_results.json`, two PDF/PNG diagnostic figures, and `qa/execution_manifest.json`.

- [ ] **Step 1: Add a failing bootstrap test**

Assert that ten requested replicates produce ten finite rows, duplicated scenes receive distinct replicate identifiers, and track weights still sum to one per replicated track.

- [ ] **Step 2: Run the test and verify failure**

Run: `python -m unittest tests.test_scientific_risk_core.SceneBootstrapTests -v`

- [ ] **Step 3: Implement bootstrap and the artifact runner**

Use seed `2026091301` for model comparison and `2026091302` for the 1000-replicate scene bootstrap. Generate a compact GMM LOSO-NLPD figure and a power-delay held-out-RMSE/breakpoint figure. Record the input hash and every output hash.

- [ ] **Step 4: Run tests and then the experiment runner**

Run: `python -m unittest discover -s tests -v`

Run: `python scripts/run_scientific_risk_experiments.py`

### Task 5: Independent QA and scientific gate report

**Files:**
- Create: `tests/test_independent_qa.py`
- Create: `scripts/run_independent_qa.py`
- Create by the QA runner: `qa/independent_qa.json`
- Create by the QA runner: `qa/independent_qa_report.md`

**Interfaces:**
- `audit_outputs(output_root: Path, source_path: Path) -> dict`

- [ ] **Step 1: Write a failing QA test against a deliberately incomplete fixture**

Assert that missing scene folds, a non-unit track-weight sum, non-finite parameters, or fewer than 1000 bootstrap replicates produces `FAIL`.

- [ ] **Step 2: Run the QA test and verify failure because the auditor is absent**

Run: `python -m unittest tests.test_independent_qa -v`

- [ ] **Step 3: Implement the independent auditor**

The auditor must independently reload the source, confirm 518/346/172/236/9, verify all nine scene folds for each candidate, verify train/test scene disjointness, check finite model values and ordered means, verify 1000 bootstrap replicates for every requested fit, compare recorded hashes, and confirm the source hash is unchanged.

- [ ] **Step 4: Run all tests, execute QA, and inspect figures**

Run: `python -m unittest discover -s tests -v`

Run: `python scripts/run_independent_qa.py`

Expected: `PASS` or `PASS_WITH_LIMITATIONS`; scientific interpretation remains blocked if QA returns `FAIL`.

### Task 6: Final verification and author-facing result

**Files:**
- Create with `apply_patch`: `qa/SCIENTIFIC_GATE_REPORT.md`

**Interfaces:**
- Consumes all Task 4-5 artifacts.
- Produces an evidence-bounded decision for each current paper model: supported, mixed, or unsupported.

- [ ] **Step 1: Compare the result tables with the predeclared rules**

Report the LOSO differences without hiding unfavorable folds. State explicitly whether K=2 is selected by the one-standard-error rule and whether the fixed two-line fit improves held-out RMSE over one line.

- [ ] **Step 2: Render and inspect both figures**

Check labels, legends, environment separation, finite ranges, and absence of clipped content.

- [ ] **Step 3: Run final hashes and source-integrity checks**

Run the complete tests and independent QA once more after the report is written.

- [ ] **Step 4: Stop at the author gate**

Do not edit the manuscript. Present the isolated experiment outputs and identify exactly which, if any, results are suitable for later insertion.

