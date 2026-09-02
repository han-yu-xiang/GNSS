# Environment-Conditioned Lock-Loss Model Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and validate a versioned, environment-conditioned lock-loss entry-rate and duration model from existing GNSS-SDR tracking outputs without reading raw IQ or changing SAGE production artifacts.

**Architecture:** A standalone Python analysis tool will resolve the 63 modeling-eligible tracking MAT files through the frozen event-database and scene-context provenance, extract finite carrier-lock observations on the sample-counter time axis, classify gaps and censoring explicitly, and publish per-run exposure/event tables plus environment-level semi-Markov parameters. The tool will use a deterministic Gamma-Poisson entry-rate estimate and compare common duration families with censored-likelihood support; it will not alter the full SAGE pipeline or infer physical LOS loss.

**Tech Stack:** Python 3.12, NumPy/SciPy from `D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe`, `scipy.io.loadmat`, standard-library CSV/JSON/hash/time utilities, pytest/unittest.

**Spec:** Prior approved environment-conditioned binary semi-Markov lock-loss design in the active task context; source facts are frozen in `docs/GNSS_SAGE_ENGINEERING_HANDOFF_CURRENT.md` Sections 48--51 and the alignment partition.

## Global Constraints

- Read only existing tracking MAT, event-database provenance, scene-context metadata, and source code; do not read raw IQ.
- Do not run MATLAB, SAGE, batch production, or modify `run_nav_sage_pipeline.m`, metadata, inventory, or existing SAGE artifacts.
- Exclude the G06 legacy run from modeling because its `run_context.json` is absent; retain it only as an explicit excluded record.
- Use `carrier_lock_test < -0.5` as the receiver diagnostic bad-lock definition, not as proof of physical signal disappearance.
- Time durations come from `PRN_start_sample_count / sample_rate_hz`; gaps are `INCONCLUSIVE_GAP` and are never bridged.
- Preserve left/acquisition and right/terminal censoring; never truncate or pad observations.
- Write only to new `dataset_generation_logs/channel_modeling/environment_lock_model_v1_20260826/` and a uniquely responsible report/script/test; refuse to overwrite an existing namespace.
- The lock-loss model is distinct from the overall multipath channel model; leave path/elevation statistical-model status unchanged except for recording this new bounded result.

### Task 1: Freeze source resolution and label semantics

**Files:**
- Create: `scripts/analysis/build_environment_lock_model.py`
- Test: `scripts/analysis/test_build_environment_lock_model.py`

**Interfaces:**
- `resolve_modeling_runs(project_root: Path) -> list[RunInput]`
- `classify_lock_states(lock_values: Sequence[float], times_s: Sequence[float], threshold: float, gap_limit_s: float) -> list[LockSegment]`
- `extract_run_observations(mat_path: Path, expected_prn: str, sample_rate_hz: int) -> RunObservation`

- [ ] **Step 1: Write failing tests for strict input selection and lock labeling.**

  Add tests that assert the resolver returns 63 modeling-eligible rows, excludes the one G06 legacy row with an explicit reason, rejects a PRN mismatch, maps `carrier_lock_test=-0.5` to good and a lower finite value to bad, maps non-finite values to inconclusive, and splits a timeline at a gap greater than the frozen continuity limit.

- [ ] **Step 2: Run the focused tests and verify they fail because the new interfaces do not exist.**

  Run: `D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe -m pytest scripts\analysis\test_build_environment_lock_model.py -q`

  Expected: collection or attribute failures naming the missing resolver/label functions.

- [ ] **Step 3: Implement only source resolution and label functions.**

  Read `facts/sage_runs.csv` and `exports/modeling_run_eligibility.csv`, join by `run_id`, join `dimensions/scene_context.csv` by `scene_id`, and retain absolute tracking paths only when they exist and are non-empty. Resolve G06 as `excluded_legacy_context_missing`. Define `LOCK_GOOD`, `LOCK_BAD`, `INCONCLUSIVE`, and `INCONCLUSIVE_GAP` without reading any Stage4 labels.

- [ ] **Step 4: Run the focused tests and verify they pass.**

  Run the same pytest command; expected: all Task 1 tests pass.

### Task 2: Extract run exposure and censored outage events

**Files:**
- Modify: `scripts/analysis/build_environment_lock_model.py`
- Test: `scripts/analysis/test_build_environment_lock_model.py`

**Interfaces:**
- `extract_run_observations(...) -> RunObservation`
- `build_exposure_and_events(observation: RunObservation, debounce_bad_ms: int, reacquire_good_ms: int) -> tuple[ExposureRecord, list[EventRecord]]`

- [ ] **Step 1: Write failing tests for sample-counter durations and censoring.**

  Add synthetic tracking arrays with a 1 ms cadence, an internal 3 ms bad run, a terminal bad run, an initial acquisition prefix, and a large time gap. Assert that durations use seconds from sample counters, the acquisition prefix is not an entry event, terminal loss is `right_censored=true`, and gap-separated data is not merged.

- [ ] **Step 2: Run the focused tests and verify the new extraction interfaces fail.**

  Run: `D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe -m pytest scripts\analysis\test_build_environment_lock_model.py -q`

- [ ] **Step 3: Implement MAT field loading and event extraction.**

  Load only tracking MAT fields required by the model (`PRN`, `PRN_start_sample_count`, `carrier_lock_test`, with C/N0 retained for audit). Validate expected PRN, sort by sample time only when source order is monotonic-equivalent, compute the median positive interval and continuity threshold, apply fixed 20 ms bad-entry/100 ms good-reacquisition debounce, and mark start/end censoring. Preserve run, scene, PRN, channel, environment, acceptance class, source path and source hash provenance.

- [ ] **Step 4: Run focused tests and verify pass.**

  Run the same pytest command; expected: all extraction/censoring tests pass.

### Task 3: Fit environment-level entry and duration models

**Files:**
- Modify: `scripts/analysis/build_environment_lock_model.py`
- Test: `scripts/analysis/test_build_environment_lock_model.py`

**Interfaces:**
- `fit_entry_rate(exposures: Sequence[ExposureRecord], events: Sequence[EventRecord], prior: GammaPrior) -> list[EnvironmentParameter]`
- `fit_duration_models(events: Sequence[EventRecord], families: Sequence[str]) -> list[EnvironmentParameter]`
- `derive_environment_parameters(...) -> list[EnvironmentParameter]`

- [ ] **Step 1: Write failing tests for zero-event environments, duration-family fit, and derived occupancy.**

  Test Gamma-Poisson conversion, a zero-entry group with finite prior output, positive-duration validation, right-censored survival contribution, one common selected duration family across environments, and the consistency relationship between entry rate, mean duration, and occupancy.

- [ ] **Step 2: Run focused tests and verify the fit interfaces fail.**

  Run the same pytest command; expected: missing-interface failures.

- [ ] **Step 3: Implement deterministic fitting.**

  Estimate environment entry rates using a documented Gamma prior and exposure seconds; convert to per-ms entry probability. Compare lognormal, Weibull and gamma duration likelihoods with right-censored events, select one family globally using AICc with a deterministic tie-break, and estimate environment parameters with partial pooling/shrinkage. If support is too weak, emit an empirical/`PRIOR_DOMINANT` status rather than a fabricated precise fit. Keep sample-weighted occupancy and run-level summaries separate.

- [ ] **Step 4: Run focused tests and verify pass.**

  Run the same pytest command; expected: all fitting tests pass.

### Task 4: Add CLI, immutable output namespace, provenance and QA

**Files:**
- Modify: `scripts/analysis/build_environment_lock_model.py`
- Test: `scripts/analysis/test_build_environment_lock_model.py`
- Create at runtime only: `dataset_generation_logs/channel_modeling/environment_lock_model_v1_20260826/`

**Interfaces:**
- `build_model(project_root: Path, output_dir: Path) -> BuildResult`
- CLI: `python build_environment_lock_model.py --project-root E:\\GNSS_Multipath_Project --output <new namespace>`

- [ ] **Step 1: Write failing tests for namespace protection and output schema.**

  Assert an existing output directory is rejected without modification, the manifest records all source hashes and `raw_iq_read=false`, output CSVs have stable headers, excluded G06 is visible, and no output path is under `scenes/**/sage_results`.

- [ ] **Step 2: Run focused tests and verify the CLI/output tests fail.**

  Run the same pytest command; expected: missing build/manifest behavior.

- [ ] **Step 3: Implement output publication.**

  Refuse overwrite, write `lock_exposure_by_run.csv`, `lock_event_catalog.csv`, `environment_lock_model_parameters.csv`, `lock_model_manifest.json`, `lock_model_qa_report.md`, and `run_receipt.json`. Include source paths/hashes, input run counts, field availability, threshold/debounce/gap semantics, model-family selection, all environment counts, execution flags, script hash and output hashes. Publish atomically within the new namespace and never touch SAGE directories.

- [ ] **Step 4: Run the focused tests and verify pass.**

  Run the same pytest command; expected: all output/provenance tests pass.

### Task 5: Run the real tracking-only build and complete QA

**Files:**
- Create: `docs/ENVIRONMENT_CONDITIONED_LOCK_MODEL_V1_REPORT.md`
- Modify: `docs/GNSS_SAGE_ENGINEERING_HANDOFF_CURRENT.md`
- Modify: `docs/GNSS_SAGE_PAPER_HANDOFF_CURRENT.md`

- [ ] **Step 1: Run static compilation and all new tests.**

  Run: `D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe -m py_compile scripts\analysis\build_environment_lock_model.py scripts\analysis\test_build_environment_lock_model.py`

  Run: `D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe -m pytest scripts\analysis\test_build_environment_lock_model.py -q`

- [ ] **Step 2: Run the standalone tracking-only model build.**

  Run: `D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe scripts\analysis\build_environment_lock_model.py --project-root E:\\GNSS_Multipath_Project --output E:\\GNSS_Multipath_Project\\dataset_generation_logs\\channel_modeling\\environment_lock_model_v1_20260826`

  Expected: no raw IQ access, no MATLAB/SAGE invocation, and new-only output files in the designated namespace.

- [ ] **Step 3: Inspect QA outputs and verify scientific boundaries.**

  Confirm 63 eligible runs, explicit G06 exclusion, finite source/hash provenance, no gap bridging, censored-event accounting, per-environment entry/duration parameters, uncertainty/support flags, and no elevation-conditioned claim. Confirm the existing production pipeline hash and SAGE output trees are unchanged.

- [ ] **Step 4: Write the report and synchronize authoritative handoffs.**

  Report the built model as a bounded environment-conditioned lock diagnostic/simulation layer, not as a complete multipath channel model. Update Engineering Handoff with code/output/hash/status; update Paper Handoff only to record the new validated, limited lock-loss modeling fact while preserving `STATISTICAL_CHANNEL_MODEL` for path/channel modeling as not complete. Do not update `PAPER_WORKSPACE_INDEX.md` because no paper asset structure changes.

- [ ] **Step 5: Run final verification before claiming completion.**

  Run `git diff --check`, re-run `py_compile` and the full new test file, hash the new outputs, and verify with a read-only file listing that no `scenes/**/sage_results`, raw files, production requests or existing artifacts changed.

## Self-Review Checklist

- [ ] Every new behavior has a test that was observed failing before implementation.
- [ ] All 63 modeling-eligible tracking runs are resolved from provenance; G06 is excluded explicitly.
- [ ] No raw IQ, MATLAB, SAGE, batch, or 20.46 MHz work is performed.
- [ ] Entry probability and duration are modeled separately; independent per-ms Bernoulli is not used.
- [ ] Time gaps and acquisition/terminal censoring are explicit.
- [ ] Small-sample environments use support/prior flags rather than fabricated certainty.
- [ ] New output namespace is immutable/new-only and hashes all inputs/outputs.
- [ ] The full multipath statistical channel model remains distinct and not claimed complete.
