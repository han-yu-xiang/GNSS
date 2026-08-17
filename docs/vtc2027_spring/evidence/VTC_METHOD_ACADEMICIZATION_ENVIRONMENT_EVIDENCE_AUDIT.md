# VTC Method Academicization & Environment Evidence Expansion Audit Report

Audit date: 2026-08-16  
Scope: paper-source academicization and read-only census of existing full Stage0--Stage4 artifacts  
Raw IQ read: **No**  
New SAGE execution: **No**

## 1. User-requested manuscript changes

1. The abstract no longer enumerates five paths, a zero-event case, or a rejection example. It now centers the paper on real dynamic GPS L1 C/A raw-IQ measurements, NAV-aided observation formation, SAGE path extraction, temporal/joint reliability, and path-level delay/Doppler/power/coherence observations.
2. Section II no longer repeats the raw-IQ processing chain as a standalone block. It retains one natural transition sentence referring to Fig. 1.
3. Section III now describes the implemented SAGE estimator itself, including path-wise hidden-signal formation, normalized delay--Doppler search, fractional-delay replicas, complex-gain least squares, iterative refinement, and model-order selection.
4. Engineering labels Stage0--Stage4 remain unchanged in code and artifacts but are replaced in the main scientific narrative by functional names. Figure 1 and Figure 3 were regenerated with the same underlying evidence and new scientific labels.
5. Figure 2 retains its data and geometry; its caption now states only the scientific case and the displayed direct/secondary path quantities. Figure 4 was upgraded to a four-environment descriptive plot from the new read-only census.

## 2. New abstract

### English source text

> Characterizing GNSS multipath from real vehicular raw-IQ measurements is difficult because reflected components evolve with motion while receiver-level indicators do not expose individual propagation paths. This paper evaluates a navigation-aided hierarchical SAGE framework for GPS L1 C/A raw-IQ measurements. Tracking and telemetry products, together with decoded navigation symbols, provide PRN/time alignment for NAV wiping and valid 40-ms observation-window construction, while PRN/channel association selects the intended stream. Candidate-window screening, fractional delay--Doppler SAGE estimation, temporal consistency validation, and multi-snapshot joint confirmation progressively refine the path set. The resulting confirmed observations expose excess delay, relative Doppler, relative power, and coherence at the path level. These measurements provide a basis for comparing multipath behavior across the evaluated dynamic vehicular environments.

### Chinese review text

> 从真实车辆动态原始 IQ 测量中表征 GNSS 多径具有挑战性，因为反射分量会随运动演化，而接收机层面的指标不能直接揭示单条传播路径。本文评估一种面向 GPS L1 C/A 原始 IQ 测量的导航信息辅助层级式 SAGE 框架。跟踪和遥测产品结合解码后的导航符号，为 NAV 擦除和完整 40 ms 观测窗口构造提供 PRN/时间对齐，PRN/通道关联用于选择目标信号流。候选窗口筛选、分数时延—多普勒 SAGE 估计、时间一致性验证以及多快照联合确认逐步收敛路径集合。最终确认观测提供路径级超额时延、相对多普勒、相对功率和相干度。这些测量为比较所评估动态车载环境中的多径行为提供基础。

## 3. Stage terminology replacement

| Internal stage | Scientific term used in the paper |
|---|---|
| Stage0 | NAV-Aligned Observation Formation |
| Stage1 | Candidate-Window Screening |
| Stage2 | Local SAGE Multipath Estimation and Model-Order Selection |
| Stage3 | Temporal Consistency Validation |
| Stage4 | Multi-Snapshot Joint Path Confirmation |

`STAGE_NUMBER_USAGE_IN_MAIN_TEXT = 0` for the primary English narrative after this update. Internal stage numbers remain in source code, artifact filenames, evidence ledgers, QA documents, and the reproducibility audit where they are needed for traceability.

## 4. SAGE algorithm enhancement

The current MATLAB source supports the following scientific description:

- Signal model: a direct component plus additional components with complex gain, delay, and Doppler offset relative to the direct component.
- Path-wise update: for the selected path, the implementation subtracts synthesized contributions of all other current paths to form a hidden/residual observation.
- Objective: normalized correlation energy over delay and Doppler; the coarse grid uses FFT/IFFT correlation and local refinement uses explicit fractional-delay replicas.
- Gain update: the current replica matrix is solved with the MATLAB least-squares backslash operator, yielding complex gain amplitude and phase.
- Iteration: at most 10 SAGE iterations, or early stop when relative residual-RSS change is below `1e-6`.
- Model order: local `L=1,2,3,4`; sequential order increase requires a valid model, BIC gain at least 10, and incremental RSS reduction at least 0.002 percent.
- Reliability: valid NAV-aligned observations, candidate screening, temporal matching, and five 20-ms joint snapshots are separate evidence functions. A local high-order model or temporally reliable center is not a confirmed path.
- Confirmation: only a valid joint solution containing a secondary component that satisfies the joint-confirmation path-table criterion enters the confirmed set.

These statements were checked against `scripts/sage_pipeline/run_nav_sage_pipeline.m`; no estimator logic was modified.

## 5. M-01 reproducibility update

`M01_STATUS = COMPLETED_FOR_CORE_METHOD / OPTIONAL_ENGINEERING_DETAIL_REMAINS`.

The paper now states the core reproducibility parameters that materially define the estimator: 40-ms observation windows, five 20-ms joint snapshots, 10 samples/chip at 10.23 MHz, local delay step 0.1 sample, local Doppler neighborhood ±30 Hz with 5 Hz step, model orders `L=1..4`, BIC/RSS order rules, maximum 10 SAGE iterations, RSS stopping tolerance, temporal tolerances, and joint snapshot wins. The complete A/B/C parameter classification is recorded in [SAGE_REPRODUCIBILITY_PARAMETER_AUDIT.md](SAGE_REPRODUCIBILITY_PARAMETER_AUDIT.md). Checkpoint names, wrapper policy, serialization and MATLAB process details remain engineering provenance rather than main-paper content.

## 6. Figure updates

- **Figure 1:** regenerated from the same workflow source with functional labels: Raw GPS L1 C/A IQ, GNSS tracking/NAV decoding, NAV-aligned observation formation, candidate-window screening, SAGE delay--Doppler estimation, temporal consistency validation, multi-snapshot joint confirmation, and path parameters.
- **Figure 2:** data unchanged; caption cleaned to describe the representative G25 direct/secondary path and extracted quantities without layout rationale.
- **Figure 3:** regenerated as “Hierarchical candidate reduction and path confirmation”; valid observations, candidate windows, temporal support, joint support, and confirmed paths/events are the primary labels. Local model-order evaluations are a side annotation, not a unique-object stage.
- **Figure 4:** new `figure4_environment_path_characteristics.pdf/png`, generated from the Tier A+B path census. It contains four descriptive panels: excess delay, relative power, signed relative Doppler, and coherence, with within-environment medians. No KDE, distribution fit, regression, occurrence-rate normalization, or geometry conditioning is used.

The figure generation manifest and relative-Doppler source-field audit were regenerated. The plotted signed relative Doppler is the Stage4 path offset field, not absolute carrier Doppler.

## 7. Existing environment evidence census

The census scans all currently discovered complete Stage0--Stage4 task outputs, not only the frozen five-path VTC package. It contains 18 unique scene--PRN--channel tasks and 29 unique confirmed-path rows. The primary descriptive comparison uses Tier A+B; Tier C is kept in the census but excluded from the main comparison.

| Environment | N_SCENES | N_TASKS | Valid observation windows | Derived observation span (s) | N_EVENTS | N_PATHS |
|---|---:|---:|---:|---:|---:|---:|
| Urban | 4 | 4 | 8,806 | 177.3805 | 7 | 7 |
| Mountain/Valley | 3 | 9 | 9,847 | 203.1606 | 13 | 14 |
| Highway/Open | 2 | 2 | 16,352 | 383.9759 | 2 | 2 |
| Special Reflective | 1 | 1 | 2,630 | 52.6202 | 2 | 2 |

The derived span is `last valid window time - first valid window time + 0.04 s`; it is not a separately measured raw recording duration. Stage0 windows overlap, so the window count is not an independent-sample count. The task, scene, event and path counts are reported separately to avoid treating paths as independent environment replicates.

## 8. Environment path-parameter summary

All values below are from Stage4 confirmed-path rows in Tier A+B. IQR uses the inclusive quartile definition. Persistence is not included because a stable, comparable persistence field was not available in the path census; no value was imputed.

| Environment | Parameter | n | Median | Min | Max | IQR |
|---|---|---:|---:|---:|---:|---:|
| Urban | Excess delay (samples) | 7 | 1.2000 | 1.0000 | 4.5000 | 0.2500 |
| Urban | Signed relative Doppler (Hz) | 7 | -3.8204 | -78.5522 | 19.9106 | 79.8206 |
| Urban | Absolute relative Doppler (Hz, derived) | 7 | 19.9106 | 3.0423 | 78.5522 | 59.7784 |
| Urban | Relative power (dB) | 7 | -6.3379 | -16.2501 | -3.2640 | 9.4496 |
| Urban | Coherence | 7 | 0.6678 | 0.1094 | 0.8809 | 0.5944 |
| Mountain/Valley | Excess delay (samples) | 14 | 1.1000 | 1.0000 | 2.5000 | 0.0000 |
| Mountain/Valley | Signed relative Doppler (Hz) | 14 | -0.4677 | -65.3357 | 49.6643 | 28.2998 |
| Mountain/Valley | Absolute relative Doppler (Hz, derived) | 14 | 17.1643 | 0.3357 | 65.3357 | 19.3932 |
| Mountain/Valley | Relative power (dB) | 14 | -10.6559 | -19.7731 | -3.1518 | 10.3317 |
| Mountain/Valley | Coherence | 14 | 0.7217 | 0.0056 | 0.8998 | 0.2689 |
| Highway/Open | Excess delay (samples) | 2 | 1.1500 | 1.1000 | 1.2000 | 0.0500 |
| Highway/Open | Signed relative Doppler (Hz) | 2 | -7.7147 | -10.7135 | -4.7159 | 2.9988 |
| Highway/Open | Absolute relative Doppler (Hz, derived) | 2 | 7.7147 | 4.7159 | 10.7135 | 2.9988 |
| Highway/Open | Relative power (dB) | 2 | -9.6202 | -11.3879 | -7.8526 | 1.7676 |
| Highway/Open | Coherence | 2 | 0.8411 | 0.8089 | 0.8734 | 0.0322 |
| Special Reflective | Excess delay (samples) | 2 | 1.1500 | 1.1000 | 1.2000 | 0.0500 |
| Special Reflective | Signed relative Doppler (Hz) | 2 | 11.8311 | 11.7154 | 11.9468 | 0.1157 |
| Special Reflective | Absolute relative Doppler (Hz, derived) | 2 | 11.8311 | 11.7154 | 11.9468 | 0.1157 |
| Special Reflective | Relative power (dB) | 2 | -6.2785 | -8.4374 | -4.1197 | 2.1588 |
| Special Reflective | Coherence | 2 | 0.8010 | 0.7937 | 0.8084 | 0.0074 |

These are descriptive summaries, not fitted distributions or significance tests. The signed Doppler field is primary; absolute relative Doppler is a derived display quantity only.

## 9. Evidence-tier decision

The formal environment comparison uses **Tier A+B**:

- **Tier A:** accepted production and controlled-acceptance tasks under the current fixed configuration;
- **Tier B:** reference and Wave-A/Wave-2A full-pipeline outputs with compatible estimator semantics and independent QA evidence;
- **Tier C:** G06 legacy baseline and the historical A3 G16 artifact with an execution-contract caveat. Tier C remains visible in the audit census but is excluded from primary environment statistics.

Tier A only would leave several environments represented by one scene or by very few confirmed paths. Tier A+B is therefore the most transparent current basis for bounded descriptive comparison, while the paper must retain the scene/task/path counts and the Tier B provenance.

## 10. Sufficiency decision

- **Urban = MARGINAL.** Four independent scenes and seven path rows are available, but the current accepted-production coverage includes a zero-event control and the path count remains small.
- **Mountain/Valley = SUFFICIENT_FOR_DESCRIPTIVE_COMPARISON.** Three independent scenes, nine compatible tasks, 13 events and 14 paths provide the broadest current compatible coverage. This is sufficient for measured descriptive ranges, not a population claim.
- **Highway/Open = MARGINAL.** Two scenes and two paths are available; one long zero-event task is useful as a control but does not increase positive-path replication.
- **Special Reflective = MARGINAL.** One scene, one task and two paths support a case description but not independent environment replication.

`ENVIRONMENT_COMPARISON_READY = YES` only for the bounded descriptive scope stated above. It is **not** ready for occurrence-rate comparison, elevation-conditioned statistics, distribution fitting, or a complete stochastic channel model.

## 11. Figure 4 redesign feasibility

`ENVIRONMENT_FIGURE4_READY_FROM_EXISTING_DATA = YES`.

The existing Tier A+B census supports a 2x2 descriptive figure with one marker per confirmed path and a within-environment median for excess delay, relative power, signed relative Doppler and coherence. The new figure is generated without raw-IQ access or new SAGE execution. It deliberately omits KDE, distribution fitting, regression, event-level elevation, and occurrence-rate normalization. The small Highway/Open and Special Reflective sample sizes remain visible rather than being hidden by a pooled summary.

## 12. Minimal additional full-SAGE plan

No additional run is authorized or required for the current frozen VTC campaign: `ADDITIONAL_SAGE_RUNS_RECOMMENDED = NO`. The following is a conditional planning note only, not an execution request.

**Minimum future plan if the Commander reopens production:**

| Environment | Minimum addition | Selection principle | Expected cost proxy |
|---|---|---|---|
| Special Reflective | One new independent scene, one single-channel 10.23 MHz task | Increase independent-scene replication; do not select by predicted multipath | Use Stage0 window count and prior full-scan task class; no exact runtime predicted |
| Highway/Open | One new independent scene, one single-channel 10.23 MHz task | Increase scene replication and retain a comparable control denominator | Use Stage0 window count; avoid known long task unless necessary |
| Urban | One new independent scene, one single-channel 10.23 MHz task | Balance scene coverage rather than targeting a positive event | Use Stage0 window count and existing Wave-A/A3 scale as a coarse planning proxy |

**Preferred future plan:** add two tasks from distinct scenes for each of the three marginal environments above, then reassess task/scene balance. Any reopened plan must exclude 20.46 MHz and unresolved multi-channel tasks, use the formal manifest, and never predict confirmed positives.

## 13. Recommended new Results structure

The results section now follows:

- **IV.A Hierarchical Path Extraction Behavior:** distinguish valid observations, candidate windows, local model-order evidence, temporal support, joint support and confirmed paths.
- **IV.B Representative SAGE-Extracted Multipath Case:** retain the G25 direct/secondary example and its verified path parameters.
- **IV.C Environment-Wise Path Characteristics:** present Table II and the four-panel descriptive Figure 4 with scene/task/path denominators.
- **IV.D Cross-Environment Observations:** discuss only observed ranges and coverage differences; explicitly exclude occurrence rates, elevation-conditioned claims and fitted statistical laws.

This keeps the VTC manuscript as a real-measurement and path-level characterization paper rather than converting it into a full statistical channel-model paper.

## 14. Compile status

- **English PDF:** `docs/vtc2027_spring/manuscript/latex/main.pdf`, 5 pages. `pdflatex -> bibtex -> pdflatex -> pdflatex` completed with exit code 0. No LaTeX errors, fatal errors, undefined citations/references, missing figures, or overfull boxes; two non-blocking underfull-box warnings remain.
- **Chinese review LaTeX:** `docs/vtc2027_spring/manuscript/latex_cn_review/main_cn_review.tex` updated and source-valid.
- **Chinese review PDF:** the existing canonical `main_cn_review.pdf` could not be overwritten because an existing file handle prevented XeTeX from opening it. A fresh review PDF was successfully compiled at `docs/vtc2027_spring/manuscript/latex_cn_review/main_cn_review_audit_20260816.pdf` using BibTeX and two subsequent XeLaTeX passes; it is 4 pages. The canonical old PDF was not silently relabeled as current.
- **Figure generation:** `generate_vtc_figures.py` compiled with the existing ChannelModeling-Agent Python environment; all four figure PDFs/PNGs were regenerated, and the relative-Doppler audit reported all plotted rows matched the Stage4 offset field.

## 15. Final decision flags

```text
SAGE_METHOD_ACADEMICIZED = YES
STAGE_ENGINEERING_TERMINOLOGY_REMOVED_FROM_MAIN_NARRATIVE = YES
ABSTRACT_REFOCUSED = YES
FIGURE2_CAPTION_CLEAN = YES
EXISTING_ENVIRONMENT_DATA_AUDITED = YES
ENVIRONMENT_COMPARISON_READY = YES (bounded descriptive scope only)
ADDITIONAL_SAGE_RUNS_RECOMMENDED = NO (current VTC production remains frozen)
NEW_SAGE_EXECUTED = NO
NEXT_VTC_DECISION_REQUIRED = YES
```

## Handoff impact

- Engineering handoff update required: **no**. No pipeline, execution, production, QA, manifest or engineering environment state changed.
- Paper handoff update required: **yes**. `docs/GNSS_SAGE_PAPER_HANDOFF_CURRENT.md` was synchronized with the census, method audit and manuscript status.
- Paper workspace index update required: **yes**. `docs/PAPER_WORKSPACE_INDEX.md` now registers the census, path-candidate library, reproducibility audit and combined audit report.

## No experiment executed

```text
raw IQ read: no
MATLAB: no
SAGE: no
batch production: no
20.46 MHz: no
production artifact modified: no
```
