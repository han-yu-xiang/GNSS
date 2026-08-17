# SAGE Reproducibility Parameter Audit

Status: `Implemented / Audited`; this document records the parameters exposed by the current MATLAB implementation. It does not change the pipeline, its thresholds, or any production artifact.

Source of truth: `scripts/sage_pipeline/run_nav_sage_pipeline.m` (pipeline version 3). Line references below refer to the current file and should be rechecked if the source changes.

## A. Parameters that should be stated in the paper

| Topic | Current implementation | Source |
|---|---|---|
| Input scope | The production pipeline currently accepts the validated 10.23 MHz path; `TrackingChannel` is explicit and `ProjectRoot` selects the project tree. | `run_nav_sage_pipeline.m:352-375` and the current production requests |
| Observation unit | Stage0 constructs complete NAV-aligned 40 ms windows. Stage4 uses five contiguous 20 ms snapshots centered on a reliable window, i.e., an approximately 100 ms joint interval. | `run_nav_sage_pipeline.m:92-116`, `1429-1467` |
| Sampling/code relation | GPS C/A nominal code rate is 1.023 MHz; `samplesPerChip = fs / 1.023e6`. At 10.23 MHz this is 10 samples/chip. | `run_nav_sage_pipeline.m:283-288` |
| Signal model | Each additional component is represented by a complex gain, delay, and Doppler offset relative to the direct component. | `run_nav_sage_pipeline.m:91-95` and `run_nav_sage_pipeline.m:1922-1927` |
| Local delay estimation | Stage2 uses a 0.1-sample grid (0.01 chip) with a local half-width of 0.8 samples; the minimum path separation is 1 sample (0.10 chip). | `run_nav_sage_pipeline.m:325-330` |
| Doppler estimation | The local SAGE Doppler search uses a ±30 Hz neighborhood with 5 Hz spacing around the tracking-referenced estimate. | `run_nav_sage_pipeline.m:328-330`, `1057-1067` |
| Candidate screening | The fast scan uses a ±125 Hz main-Doppler search at 25 Hz spacing, local refinement at 0.2-sample and 10 Hz resolution, and a residual search with 50 Hz Doppler spacing. | `run_nav_sage_pipeline.m:306-323`, `861-930` |
| Model orders | Local models with `L=1,2,3,4` are evaluated. Sequential promotion requires a valid model, BIC gain at least 10, and incremental RSS reduction at least 0.002 percent. | `run_nav_sage_pipeline.m:325-337`, `1070-1109` |
| SAGE update | For each path and iteration, the implementation subtracts the current estimates of the other paths, refines the selected path in delay and Doppler, and solves all complex gains by a least-squares backslash solve. It stops after at most 10 iterations or when relative RSS change is below `1e-6`. | `run_nav_sage_pipeline.m:331-332`, `1155-1192`, `1884-1892` |
| Temporal validation | A reliable center requires a consecutive run of at least 3 matching windows within radius 2, with delay tolerance 1.5 samples, Doppler tolerance 40 Hz, and relative-power tolerance 10 dB. | `run_nav_sage_pipeline.m:339-343`, `1341-1425` |
| Joint confirmation | Five 20 ms snapshots are jointly fitted. Joint model selection uses the same sequential BIC gain threshold and requires at least 4 snapshot wins for a higher-order model. | `run_nav_sage_pipeline.m:345-348`, `1429-1547` |
| Confirmation semantics | A path is treated as confirmed only after a valid joint result contains a secondary component and the corresponding Stage4 path record is marked as a multipath component. Local `L>=2` and reliable centers are intermediate evidence. | `run_nav_sage_pipeline.m:1509-1543` and project QA rules |

The paper should describe the estimator as a NAV-aided, fractional delay--Doppler SAGE procedure with progressive reliability checks. It should not reproduce every engineering threshold in the main text.

## B. Useful optional reproducibility details

The following details can be reported in a supplementary configuration table or implementation appendix if space permits:

- minimum C/N0 of 30 dB-Hz, minimum carrier lock of -0.5, sample-step tolerance of 2, and TOW-step tolerance of 2 microseconds;
- main-delay search range of -5 to 10 samples and maximum excess-delay search of 30 samples;
- residual screening separation of 2 samples and 40 Hz, residual-power threshold of -25 dB, base-candidate limits of 8--24, and neighbor radius 2;
- minimum multipath relative power of -25 dB and maximum path coherence of 0.98;
- maximum of 8 joint centers and 8 joint optimization iterations.

These values are implementation provenance, not independent physical claims about the environments.

## C. Engineering details not required in the main paper

The following are useful for execution and audit but should normally remain in the code, execution receipts, or engineering handoff:

- checkpoint file names and checkpoint intervals;
- `Resume`/new-only execution policy, Windows wrapper behavior, process locks, and MATLAB startup receipts;
- MATLAB table field names, internal record structures, plotting functions, and serialization details;
- raw-file seeking implementation, output-directory layout, task manifests, and per-stage progress logs.

## Algorithmic interpretation verified from code

For a current path estimate, the implementation forms a hidden signal by subtracting the synthesized contributions of the other paths. It then searches/refines the selected path in the delay--Doppler domain using normalized correlation with a fractional-delay code replica, followed by a complex least-squares gain update. In compact notation, the code is consistent with

\[
r_l^{(i)}(t)=r(t)-\sum_{k\ne l}\hat{\alpha}_k^{(i)}q(t;\hat{\tau}_k^{(i)},\hat{\Delta f}_k^{(i)}),
\]

and a normalized delay--Doppler objective of the form

\[
(\hat{\tau}_l,\hat{\Delta f}_l)=\arg\max_{\tau,\Delta f}
\frac{|q(\tau,\Delta f)^H r_l^{(i)}|^2}{q(\tau,\Delta f)^H q(\tau,\Delta f)}.
\]

The code realizes the correlation search with FFT/IFFT operations for the grid search and explicit fractional-delay replicas for local refinement. The gain vector is updated through the MATLAB least-squares operator. These equations are a scientific abstraction of the implementation; they do not introduce a different estimator.

## Scope and limitations

The audit supports an academically meaningful description of the current SAGE estimator and its hierarchical evidence logic. It does not establish event-level satellite geometry completeness: the current VTC geometry QA remains `PARTIAL`, with provisional nearest NMEA/GSV associations for the existing T1 paths. It also does not authorize new SAGE execution or change the current VTC production stop decision.
