# Wave-A 10.23 MHz Validation Report

## 1. Scope and final decision

This document consolidates the three completed Wave-A validation runs at
10.23 MHz. It is based on the existing post-execution QA reports and their
recorded execution receipts. No MATLAB/SAGE run was started while preparing
this summary, and no code, scene data, metadata, inventory, or existing SAGE
result was changed.

The three-task Wave-A set is:

| Task | Result |
|---|---|
| `F1023_V70_D0120_P7 / G16 / ch1` | PASS |
| `F1023_v50_D0127_P1 / G25 / ch0` | PASS |
| `F1023_V70_D0122_P1 / G12 / ch6` | PASS |

**Release conclusion:** 10.23 MHz SAGE execution is released for a
**controlled, serial, small-batch expansion** under the same Windows normal
user wrapper, immutable request, smoke-test, preflight, output-isolation, and
per-task QA gates. This evidence does not justify unattended full-dataset
execution. Every further task still requires a separately reviewed request
and post-run QA; 20.46 MHz Wave-B remains blocked.

## 2. Common Windows execution workflow

Each task followed the same approved execution boundary:

1. The task was selected from the reviewed plan and represented by a new
   immutable one-task execution request with a recorded SHA-256.
2. A normal Windows user, `TJ-CHANNEL\\Jing_`, manually invoked
   `Invoke-BatchSageWindows.ps1` from PowerShell 7. The Codex sandbox did not
   launch MATLAB.
3. The wrapper verified request, plan, selection, pipeline, and executor
   hashes; checked the exact scene/PRN/channel namespace; rejected existing
   output; enforced `new_only` and no resume; and retained reference-scene
   protection.
4. Before the executor was called, the wrapper ran
   `matlab -batch "disp('MATLAB_STARTUP_OK')"`. Both the marker and exit code
   `0` were mandatory.
5. The wrapper invoked the existing `run_batch_sage.py` executor for exactly
   one task. The executor performed a fresh preflight, invoked the unchanged
   `run_nav_sage_pipeline.m` with named parameters, and recorded status,
   timing, return code, errors, and output QA.
6. The three tasks were run serially. Each output directory was new and
   isolated to `scenes/<scene>/sage_results/nav_sage_v2/<PRN>`.
7. After completion, an independent read-only QA checked receipts, status
   history, task log, 21 expected output files, all Stage0--Stage4 artifacts,
   confirmed events, and cross-scene write isolation.

The wrapper/executor safety chain was therefore exercised in the environment
where MATLAB is known to work, while preserving Codex as the planning,
review, and audit layer.

## 3. Execution timing and audit roots

| Task | MATLAB execution root | MATLAB task duration | Python executor duration | MATLAB smoke |
|---|---|---:|---:|---:|
| G16 | `dataset_generation_logs/batch_sage_execution/batch_sage_execution_20260809T051102Z` | 3913.123 s (65.219 min) | 3913.409 s | 12.595 s, exit 0 |
| G25 | `dataset_generation_logs/batch_sage_execution/batch_sage_execution_20260809T064633Z` | 2724.903 s (45.415 min) | 2725.085 s | 14.074 s, exit 0 |
| G12 | `dataset_generation_logs/batch_sage_execution/batch_sage_execution_20260809T082111Z` | 2949.653 s (about 49.16 min) | 2949.850 s | 14.055 s, exit 0 |

The three MATLAB task durations sum to `9587.679` seconds, approximately
159.795 minutes. All three MATLAB task return codes were `0`; all three Python
executor return codes were `0`; and all three status histories ended with
`matlab_exit_0_and_output_qa_pass`.

Authoritative task-specific QA documents:

- [Pilot-1 G16 QA](E:\GNSS_Multipath_Project\docs\PILOT1_G16_QA_REPORT.md)
- [Wave-A G25 QA](E:\GNSS_Multipath_Project\docs\WAVEA_G25_QA_REPORT.md)
- [Wave-A G12 QA](E:\GNSS_Multipath_Project\docs\WAVEA_G12_QA_REPORT.md)

## 4. Consolidated Stage0--Stage4 results

All three output directories contain the expected 21 non-empty target files,
including run context, Stage0--Stage4 CSV/MAT outputs, progress records,
Doppler-sign data, and overview imagery.

| Task | Stage0 NAV symbols | 40 ms windows | Stage1 scan | Stage2 evaluations / valid / selected | Selected L1/L2/L3/L4 | L>=2 / L>=3 | Stage3 rows / pass / reliable centers | Stage4 joint / valid | Confirmed events / paths |
|---|---:|---:|---|---|---|---:|---|---|---:|
| G16 | 2231 | 2229 | 2229 valid, 0 errors | 416 / 340 / 104 | 20 / 34 / 17 / 33 | 84 / 50 | 167 / 39 / 11 | 8 / 8 | 4 / 4 |
| G25 | 2343 | 2339 | 2339 valid, 0 errors | 424 / 259 / 106 | 106 / 0 / 0 / 0 | 0 / 0 | 0 / 0 / 0 | 0 / 0 | 0 / 0 |
| G12 | 1631 | 1629 | 1629 valid, 0 errors | 428 / 356 / 107 | 21 / 17 / 12 / 57 | 86 / 69 | 212 / 65 / 11 | 8 / 8 | 3 / 3 |

Additional Stage1 residual screening counts recorded by QA were:

| Task | One-strong rows | Two-strong rows |
|---|---:|---:|
| G16 | 1866 | 1714 |
| G25 | 2120 | 2044 |
| G12 | 1458 | 1368 |

Interpretation of the table:

- G16 and G12 selected substantial numbers of higher-order models and
  produced reliable persistence centers followed by joint confirmations.
- G25 selected only L1 models. Its Stage3 and Stage4 files are complete,
  non-empty header/MAT outputs with zero event rows; this is a valid
  low-multipath/LOS-like result, not an interrupted run.
- Invalid non-selected Stage2 model rows in G16 and G25 are candidate-fit
  outcomes, not task failures. Selected windows had final models and the
  executor output QA passed.

## 5. Confirmed multipath events

The current event condition is a Stage4 row with `joint_valid=1` and
`joint_multipath_count>0`. The three Wave-A tasks produced seven confirmed
event rows and seven associated paths in total. G25 produced no confirmed
event and consequently has no path parameters to report.

### G16 — four events / four paths

| Center window | Time (s) | Joint L | Excess delay (samples / chips) | Doppler offset (Hz) | Relative power (dB) | Coherence | Paths |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1337 | 68.502853 | 2 | 1.2 / 0.12 | +19.6532 | -4.5894 | 0.6678 | 1 |
| 1338 | 68.522853 | 2 | 1.0 / 0.10 | +19.9106 | -3.2640 | 0.6829 | 1 |
| 1406 | 69.882856 | 2 | 1.1 / 0.11 | -3.0423 | -6.3379 | 0.8809 | 1 |
| 2079 | 83.342881 | 2 | 1.1 / 0.11 | -3.8204 | -5.0925 | 0.8778 | 1 |

The source QA report records these as four Stage4 event rows and four
associated multipath paths. Windows 1337 and 1338 are retained as separate
Stage4 rows; no physical-event clustering is asserted here.

### G12 — three events / three paths

| Center window | Time (s) | Joint L | Excess delay (samples / chips) | Doppler offset (Hz) | Relative power (dB) | Coherence | Paths |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 835 | 44.9110977517107 | 2 | 1.4 / 0.14 | -71.5654432731581 | -16.2501226962046 | 0.184742563164214 | 1 |
| 836 | 44.9310977517107 | 2 | 1.3 / 0.13 | -71.4648759076238 | -15.3692890811629 | 0.187127715719209 | 1 |
| 1278 | 53.7711064516129 | 2 | 4.5 / 0.45 | -78.5522071033497 | -13.2119027229851 | 0.109428071806393 | 1 |

The corresponding G12 path-level estimates are:

| Center window | Path delay (samples) | Path Doppler (Hz) |
|---:|---:|---:|
| 835 | 1.6 | -1623.0892469841 |
| 836 | 1.5 | -1623.82156536075 |
| 1278 | 4.6 | -1638.09578620491 |

All event values above were copied from the existing Stage4 QA results; no
parameter was recomputed for this report. G16 values retain the precision
recorded in its QA report, while G12 values retain the CSV-derived precision.

## 6. Role of G25 as a LOS reference

G25 is important as a negative/control case within the same Wave-A execution
framework. It completed the full pipeline with 2343 valid NAV symbols and
2339 windows, but selected only L1 models (`L>=2=0`, `L>=3=0`), had no
reliable Stage3 centers, and produced zero Stage4 joint multipath events and
paths.

This makes G25 a practical LOS/low-multipath reference for checking whether
the pipeline and event database distinguish ordinary single-path behavior from
confirmed multipath. It is not proof that G25 is physically free of every
possible reflection; the correct conclusion is limited to the current SAGE
confirmation criteria and this scene/PRN observation.

## 7. Failure experience and environment lesson

The first Wave1 batch attempt used direct `subprocess` MATLAB startup from the
Codex sandbox identity `tj-channel\\codexsandboxoffline`. All five tasks
failed before Stage0 with MATLAB return code `1` and
`System Error: File system inconsistency`. Input data and SAGE logic were not
reached.

Subsequent diagnosis showed that MATLAB R2025a Update 1 could start under the
normal Windows user `TJ-CHANNEL\\Jing_`, while the sandbox launch environment
was not a reliable MATLAB runtime. Redirecting preferences and TEMP/TMP did
not establish a safe fix for the sandbox failure. An additional smoke-test
issue was observed in which MATLAB printed its success marker but exited with
code `3` during native shutdown involving `ddux.dll`/`mwddux_matlab.dll`; the
wrapper correctly treats marker-with-nonzero-exit as failure.

The solution was an explicit Windows execution boundary:

- Codex creates and reviews immutable requests and performs planning/audit;
- `TJ-CHANNEL\\Jing_` runs the PowerShell wrapper manually;
- the wrapper validates identity, hashes, namespace, input/output gates, and
  locks;
- MATLAB must pass both startup marker and exit code `0`;
- only then does the existing Python executor call the unchanged SAGE
  pipeline.

This architecture converted the three approved tasks into successful,
auditable runs without changing the SAGE algorithm or bypassing the exit-code
gate.

## 8. Operational release conditions

The Wave-A result supports the following controlled release:

- permit additional **10.23 MHz** tasks only as reviewed, one-task immutable
  requests executed serially by the normal Windows user;
- require validation-only review before every execute command;
- require MATLAB smoke marker plus exit `0`, Python executor exit `0`, and
  per-task Stage0--Stage4/output QA;
- preserve new-only output behavior, exact output namespace, reference-scene
  protection, no automatic resume, and failure isolation;
- keep 20.46 MHz tasks blocked until sampling-rate support and a separate
  validation plan are approved;
- do not treat this three-task sample as representative of all scenes or
  environments.

The next research-facing step is to connect these validated outputs to the
planned multipath-event database schema, while retaining the raw Stage4
provenance and the G25 control label.
