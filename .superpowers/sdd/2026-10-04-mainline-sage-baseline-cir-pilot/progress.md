# SDD ledger — plan: docs/superpowers/plans/2026-10-04-mainline-sage-baseline-cir-pilot.md

## Pre-flight

- Worktree: normal checkout on `review/vtc-final-language-layout-cleanup-20260917`; existing dirty files and untracked user assets preserved.
- Ruling: stay in the fixed project checkout — the frozen pipeline, manifest, raw scene, archive, and output namespace are canonical under `E:\GNSS_Multipath_Project`; a separate worktree would not contain the same authoritative data and would redirect required outputs. Cost if wrong: less isolation from unrelated user edits; mitigate by touching only plan-approved new paths and rechecking status.
- Ruling: use the seven numbered implementation-plan steps directly — installed execution helper set has `sdd-workspace`, `task-brief`, and `review-package` but no `task-start` or `task-done`, and the approved plan uses numbered steps rather than `Task N` headings. Cost if wrong: less automated task bookkeeping; this ledger records each step and evidence.
- Commit/push: prohibited by user; no commits or pushes will be made.

## Shared interfaces

1. Preflight -> wrapper: exact 89-row manifest entry, frozen source SHA, required input paths, absent staging/final namespace.
2. Wrapper -> single run: one `F1023_V70_D0117_P2 / G28 / ch1`, explicit `Resume=false`, Stage0–Stage4 completeness, relocation receipt.
3. Run -> regression: final relocated outputs compared read-only against the archived G28/ch1 baseline.
4. Regression -> sidecars/ledger: CIR, alpha export, and ledger are gated on `PASS_EXACT` only.
5. Sidecars -> validation: CIR HDF5/metadata, Stage0-aligned 40 ms PDP, complex alpha provenance.
6. Stage outputs -> ledger: every Stage2 selected path retained; four classes and exact row-count conservation; Stage4 is not a modeling hard gate.

## Steps

- Step 1 — preflight: COMPLETE; exact target manifest row and all required inputs validated, including metadata sample rate 10.23 MHz, `mapping_warning=NONE`, absent staging/final namespaces, and frozen-source SHA.
- Step 2 — wrapper and tests: PARTIAL; 10/10 Pester checks pass, but actual MATLAB native-argument transport exposed that embedded double quotes in the MATLAB expression are stripped. Wrapper currently fails closed at MATLAB parse time and needs a quoting fix plus a test that verifies the argument survives transport.
- Step 3 — one frozen SAGE run: BLOCKED; MATLAB startup smoke passed, but the one target invocation failed with a MATLAB syntax error before `run_nav_sage_pipeline` could execute. No automatic retry per execution guardrail.
- Step 4 — exact baseline comparison: NOT_STARTED.
- Step 5 — CIR and complex-alpha sidecars: NOT_STARTED.
- Step 6 — complete modeling ledger: NOT_STARTED.
- Step 7 — validation and reports: NOT_STARTED.

## Attempt outcome / preserved state

- MATLAB startup smoke: passed (`MATLAB_STARTUP_OK`, exit code 0).
- Actual batch expression reached MATLAB with string delimiters missing from the `run_nav_sage_pipeline` arguments; MATLAB reported `运算符的使用无效` and exit code 1. The SAGE function body did not execute.
- The authorized target raw IQ was read only for preflight SHA-256; no IQ samples were processed. No other dataset raw IQ was read.
- Frozen SAGE source remains unchanged at SHA-256 `bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c`.
- Both staging and final output namespaces remain absent. The run lock `.windows_runner_active.lock` remains in place fail-closed; do not remove or retry without explicit follow-up authorization.
- No baseline comparison, CIR/alpha sidecar, ledger, or execution report was produced. Archive untouched; no moves, commit, or push.
