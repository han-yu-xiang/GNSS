# Engineering handoff excerpt

Source: `docs/GNSS_SAGE_ENGINEERING_HANDOFF_CURRENT.md`, Section 103. The section below is copied verbatim; the original handoff was not modified for this publication.

## 103. Mainline frozen SAGE baseline pilot blocked before pipeline entry (2026-10-04)

- Validated the single authorized manifest row `F1023_V70_D0117_P2 / G28 / ch1`: sample rate 10.23 MHz from target metadata, all declared inputs present, `mapping_warning=NONE`, `Resume=false`, and both staging and final namespaces absent. No other task was selected.
- Frozen source `scripts/sage_pipeline/run_nav_sage_pipeline.m` remained unchanged at SHA-256 `bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c`.
- The non-admin PowerShell 7 wrapper passed its MATLAB startup smoke (`MATLAB_STARTUP_OK`, exit code 0), then the actual single-task MATLAB batch command failed at parse time: native argument transport stripped the double-quote delimiters around MATLAB string arguments, producing `运算符的使用无效` and exit code 1. `run_nav_sage_pipeline` did not enter; no Stage0–Stage4 computation occurred. Do not infer a SAGE regression result from this attempt.
- The authorized target raw IQ was streamed only for preflight SHA-256; IQ samples were not decoded or processed. No other dataset raw IQ was read. No GNSS-SDR, other SAGE task, or 20.46 MHz task ran.
- Both the transient and final SAGE output namespaces remain absent; archive is untouched. The global `.windows_runner_active.lock` remains fail-closed after the failed invocation and must not be cleared or retried without explicit follow-up authorization.
- Wrapper safety tests currently pass 10/10 but did not exercise Windows PowerShell-to-MATLAB native argument preservation; add that regression test before any rerun. Baseline comparison, CIR/alpha sidecars, modeling ledger, and requested pilot reports were not produced.
- No frozen algorithm/source edit, commit, or push occurred. The current attempt is blocked pending a tested argument-quoting correction and authorized continuation.

```text
MAINLINE_BASELINE_PILOT=BLOCKED_BEFORE_SAGE_ENTRY
MAINLINE_BASELINE_REGRESSION=NOT_RUN
FROZEN_SAGE_SHA256=bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c
RAW_IQ_BYTES_READ_FOR_SHA256=YES_TARGET_ONLY
RAW_IQ_SAMPLE_DECODE=NO
OTHER_RAW_IQ_READ=NO
STAGE0_STAGE4=NOT_RUN
CIR_ALPHA_LEDGER=NOT_CREATED
GNSS_SDR_EXECUTED=NO
OTHER_88_SAGE_TASKS=NOT_RUN
SAGE_2046_MHZ=NOT_RUN
COMMIT_PUSH=NO
NEXT_ACTION=FIX_AND_TEST_MATLAB_ARGUMENT_TRANSPORT_THEN_REQUEST_AUTHORIZED_CONTINUATION
```
