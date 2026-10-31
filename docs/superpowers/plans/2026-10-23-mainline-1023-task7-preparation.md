# Mainline 10.23 MHz Task 7 Preparation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prepare a Stage2-specific modeling contract and tested pure-Python utilities without fitting a model or disturbing Task 5 CIR production.

**Architecture:** A small standard-library module will operate on caller-provided Stage2 ledger rows and independently validated CIR window-index evidence. It will derive counts only for represented Stage2 windows, create scene-blocked LOSO index folds, and annotate every MPC row with one explicit association state. A design document will record the estimand, coverage, candidate distributions, support limits, and future gates.

**Tech Stack:** Python 3 standard library, `unittest`, Markdown.

**Spec:** `docs/superpowers/specs/2026-10-23-mainline-1023-stage2-model-preparation-design.md`

## Global Constraints

- Do not interrupt or modify Task 5 CIR production, its release, source, worker, monitor, or outputs.
- Do not run MATLAB/SAGE, read raw IQ, or open/read/deserialize MAT/HDF5/CIR payloads.
- Keep Stage2 as a selected population; do not add unselected Stage0 windows as zero-MPC observations.
- Use scene as the holdout unit; preserve all rows and distinguish path-, window-, run-, and scene-level observations.
- Use exact `(run_id, window_id)` CIR keys and retain every Stage2 MPC row.
- Do not perform formal fitting, training, significance testing, Gate F, or model validation; Phase-2 generative training remains unauthorized.
- Use only the Python standard library; keep changes isolated to the Task 7 preparation module, its synthetic tests, the design, and an append-only engineering handoff entry.

## Review Focus

- Duplicate or malformed `(run_id, window_id, path_id)` input must fail rather than silently inflate or collapse counts.
- A Stage0-only window must never enter the selected-window count population.
- All runs/windows/paths from one scene must remain wholly inside one LOSO test fold.
- Reused `window_id` values across runs must not cross-associate; unvalidated runs must remain `UNASSOCIATED`.
- Association must preserve row count, order, and input values, including rows with no validated CIR correspondence.

---

### Task 1: Stage2 model-preparation utilities and evidence

**Files:**
- Create: `scripts/channel_modeling/mainline_stage2_model_prep.py`
- Create: `scripts/channel_modeling/tests/test_mainline_stage2_model_prep.py`
- Create or refine: `docs/superpowers/specs/2026-10-23-mainline-1023-stage2-model-preparation-design.md`
- Modify: `docs/GNSS_SAGE_ENGINEERING_HANDOFF_CURRENT.md` (append one dated Task 7 preparation status only)

**Interfaces:**
- `mpc_counts_by_selected_window(rows) -> dict[tuple[str, str], int]`: count `is_multipath` rows only for unique represented `(run_id, window_id)` pairs; require positive canonical decimal window IDs; reject duplicate path identities and malformed rows.
- `leave_one_scene_out_folds(rows) -> list[dict]`: return deterministic scene-keyed train/test row-index lists; every row in the held scene is test-only; require at least two nonempty scenes and one consistent scene label per run_id.
- `build_validated_cir_window_index(run_evidence) -> tuple[set[str], set[tuple[str, str]]]`: trust a run only when expected, receipt, and HDF5 run IDs agree; task receipt and HDF5 read-back are PASS; and Stage0/PDP window ID sequences match exactly with unique IDs. A purported PASS with mismatched identity or sequences raises an error.
- `annotate_cir_association(rows, validated_runs, validated_window_keys) -> list[dict]`: return a copy of every row, preserving order, with `UNASSOCIATED`, `NO_CIR_CORRESPONDENCE`, or `ASSOCIATED_VALIDATED` based only on exact run/window identity.

- [ ] **Step 1: Write synthetic tests first** for selected-window-only counts (including represented zero-MPC window), duplicate/malformed/noncanonical identity rejection, scene-atomic LOSO and conflicting run/scene labels, exact cross-run window-key isolation, all three CIR states, invalid PASS index rejection, and row/order preservation.
- [ ] **Step 2: Run the focused test module** and confirm it fails because the new functions do not exist.
- [ ] **Step 3: Implement the minimal pure-standard-library helpers** with explicit input validation and no filesystem or HDF5 access.
- [ ] **Step 4: Run the focused test module** and confirm all synthetic tests pass.
- [ ] **Step 5: Record evidence in the design and engineering handoff**, including the Stage2 selection/coverage frame, scene/elevation support, candidate families/metrics, association semantics, and an explicit statement that Gate F and fitting remain pending.
- [ ] **Step 6: Run focused verification and commit only the Task 7 preparation plan/design, module, test, and handoff update**; leave pre-existing untracked MATLAB files untouched.

Run: `python -m unittest scripts.channel_modeling.tests.test_mainline_stage2_model_prep -v`

Expected: the pre-implementation run fails on missing helper imports; the final run passes all synthetic tests.

Commit: `feat: prepare scene-safe Stage2 modeling utilities`
