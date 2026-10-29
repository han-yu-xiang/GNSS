# Mainline Stage2 Gate G Supplement Implementation Plan

**Goal:** Test count-conditioned Stage2 MPC mark prediction and discrete-delay Gaussian-copula scoring on the frozen 13-scene population, then issue an evidence-bounded Gate G recommendation.

**Spec:** `docs/superpowers/specs/2026-10-30-mainline-stage2-gateg-supplement-design.md`

**Base:** `e0b22b43ec2ac58253ce1f41e933bf41734f9c44`

**Execution outcome (2026-10-30):** The count-conditioned and delay-cell-score analysis, focused tests, independent score reconciliation, report and authority-doc updates are complete. Gate G remains `PENDING`: source/data screening found a likely window-shifted 5-Hz relative-Doppler lattice, while the approved mixed score treats Doppler continuously. The computed Copula/affected count-conditional scores are therefore provisional and are not accepted as decisive evidence. See the final scientific review in the result package; no production data or process was touched.

## Global constraints

- Work only in the existing `review/gnss-mainline-cir-model-20261022` worktree.
- Read only the frozen light CSV inputs. No MAT/HDF5/raw IQ, SAGE, CIR, alpha, or WP1–WP6 reruns.
- Never overwrite old result packages. Create one new supplemental output package.
- Use complete-scene outer LOSO and training-only nested scene-LOSO selection.
- Preserve Stage2 selection conditioning, every row, failures, low support, and rank semantics.
- Use TDD for new scoring logic. Run only focused tests plus relevant WP6 tests.
- Commit only this supplement's code/tests/report/compact outputs and the three authority docs; preserve unrelated untracked work.
- Push normally to the existing branch and update the existing Draft PR #2; do not merge.

## Tasks

### Task 1 — Synthetic tests for quantized delay and mixed copula score

**Files:** add `scripts/channel_modeling/tests/test_mainline_stage2_wp6_gateg.py`.

Write failing tests first for delay lattice validation and truncation; discrete
bin masses; stable interval probability; independence identity of the mixed
score; hand-checkable bivariate/conditional-normal calculations; positive
definiteness and invalid-grid rejection; exact identity and count/rank grouping.

**Expected:** focused tests fail before implementation and do not touch real
scientific outputs.

### Task 2 — Tie-aware fit and score primitives

**Files:** add `scripts/channel_modeling/mainline_stage2_wp6_gateg.py`.

Implement scene/window-balanced grouped-likelihood fits for delay candidate
families, reuse existing WP3 weighted fits for continuous marks, stable
truncated grid-cell log masses, valid correlation parameterization, and exact
mixed discrete-continuous Gaussian-copula composite scores. Keep the original
WP6 implementation and outputs unchanged.

**Expected:** Task 1 tests pass; identity copula equals product score to numeric
tolerance; ties receive finite probability-mass scores rather than point
densities.

### Task 3 — Nested 13-scene count-conditioned evaluation

**Files:** extend the supplemental module and add a small runner.

For each complete-scene outer fold, select/finalize M0 and N-specific M1
margins using training scenes only; fit C0/C1 dependence on training scenes
only; score identical held-out rows. Emit fold manifests, family/parameter
tables, per-path and per-window scores, per-scene paired deltas, support and
failure tables. Add rank-by-count within-window diagnostics, explicitly
descriptive and scene-clustered.

**Expected:** 13 held-out scene identities, no fold leakage, every scored MPC
identity reconciles, no unselected windows converted into path rows, and
all per-scene outputs retain low support/failures.

### Task 4 — Independent validation, figures, report, and evidence

Add a read-only validator that recomputes score arithmetic, exact keys, held-out
scene bindings, lattice cells, paired sample equality, and rank diagnostics
from compact outputs. Run focused tests and relevant WP6 regressions. Produce
the Chinese Gate G science review, compact tables/figures, input/code hashes,
and exact command/time/exit/log records in a new output package.

**Expected:** validator agrees with result tables; all numeric claims in the
report trace to saved rows; no write to prior results or frozen inputs.

### Task 5 — Authority documents, final review, and Git delivery

Update `docs/ACADEMIC_CHANNEL_MODELING_MASTER_PLAN.md`,
`docs/GNSS_SAGE_ENGINEERING_HANDOFF_CURRENT.md`, and
`docs/GNSS_SAGE_PAPER_HANDOFF_CURRENT.md`. Run `git diff --check`, targeted
tests, review exact staged paths, and obtain a fresh whole-change review. Commit
the scoped supplement, push to the existing branch, verify remote HEAD, and
append the supplemental result/status to Draft PR #2 without merging.

**Expected:** prior findings and statuses remain accurately represented; Gate
G recommendation follows the predeclared scope; unrelated untracked files are
not staged; remote branch matches the final local commit.
