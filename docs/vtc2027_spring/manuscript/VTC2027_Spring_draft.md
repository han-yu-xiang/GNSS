# Hierarchical SAGE Extraction and Validation of GPS L1 C/A Multipath in Dynamic Road Environments

## Abstract

Characterizing GNSS multipath from real dynamic-road raw-IQ measurements is difficult because reflected components evolve with motion while receiver-level indicators do not directly resolve individual propagation paths. This paper evaluates a navigation-data-aided hierarchical SAGE framework for GPS L1 C/A raw-IQ measurements. Tracking and telemetry products, together with decoded navigation data bits, provide PRN/time alignment for navigation-bit wipe-off and construction of valid 40-ms observation windows, while PRN/channel association selects the intended stream. Candidate-window screening, fractional delay--Doppler SAGE estimation, temporal consistency validation, and multi-snapshot joint confirmation progressively refine the path set. Estimator behavior is assessed through controlled injected-path recovery on measured backgrounds and native $L=1$ versus selected-model comparisons. The confirmed paths provide estimates of excess delay, relative Doppler, and relative power for path-level comparison across the four evaluated road-environment categories.

**Keywords:** GNSS multipath; GPS L1 C/A; raw-IQ measurements; SAGE; delay--Doppler path extraction.

## I. Introduction

Global navigation satellite systems support vehicle navigation and intelligent transportation, but reflections in dynamic roadside environments make the received signal time-varying [@eissfeller1996gpsdynamic; @mora1998multipath; @beitler2015cmcd]. Buildings, terrain, vehicles, and other structures can introduce propagation components whose delay, Doppler, and power change as the antenna moves. Carrier-to-noise-density ratio ($C/N_0$), pseudorange residuals, and positioning error are useful indicators of receiver-level degradation, but they do not directly expose the propagation components responsible for an observation [@bilich2007snr; @xie2011vehicular; @beitler2015cmcd].

Real dynamic raw-IQ measurements therefore require path-level analysis that distinguishes a correlation candidate from a temporally supported component and from a jointly confirmed path. Established high-resolution parameter extraction provides the link between measured GNSS signals and propagation observations [@fleury1999sage]. This paper applies that basis to a navigation-data-aided hierarchical workflow that combines candidate screening, temporal consistency, and multi-snapshot joint confirmation for path-resolved multipath estimation.

This paper makes three contributions:

1. It presents a real-world GPS L1 C/A raw-IQ measurement and processing chain that combines GNSS-SDR tracking products with navigation-data-aided observation formation.
2. It evaluates a navigation-data-aided hierarchical SAGE processing framework with progressive candidate screening, temporal consistency checking, and multi-snapshot joint confirmation.
3. It assesses estimator behavior through controlled injected-path recovery and native model-fit support, and provides measurement-based path-level comparison of SAGE-extracted multipath parameters across representative dynamic road environments.

## II. Measurement and Experimental Setup

### A. Measurement Platform

The measurement platform used a TEST-TREE RF-Catcher V2 RF signal capture and playback device together with a GNSS dome antenna. The antenna was right-hand circularly polarized (RHCP), had a documented active gain of 40 dB, and was mounted on the vehicle roof.

### B. Signal Acquisition Configuration

The measured signal was GPS L1 C/A at a documented center frequency of 1575.42 MHz [@gpsis200n2022]. Raw samples were stored as interleaved in-phase/quadrature (I/Q) data in little-endian signed 16-bit format. The measurements analyzed in this paper use a sampling rate of 10.23 MHz (10230000 Hz).

### C. Experimental Scenarios

Measurements cover four road-environment categories: dense urban roads, mountain/valley roads, open/highway roads, and Reflective-Feature scenarios containing prominent surrounding structures or surfaces that can support strong reflections. In the evaluated data, this category includes a bridge over a wide water surface and an urban road near railway and communication infrastructure.

### D. Processing Overview

The overall measurement and processing framework is illustrated in Fig. 1. Raw captures pass through GNSS-SDR tracking and navigation decoding into NAV-aligned observation formation, candidate screening, delay--Doppler estimation, and path confirmation. The GNSS-SDR support chain follows the configurable software-defined GNSS receiver architecture described in [@fernandez2011gnsssdr].

**Table I.** The measurement and processing configuration is summarized in the LaTeX manuscript.

## III. Navigation-Data-Aided Hierarchical SAGE Multipath Estimation

### A. Signal and Multipath Model

The estimator follows the space-alternating generalized expectation-maximization framework [@fessler1994sage] and its established use for high-resolution mobile-channel parameter estimation [@fleury1999sage]. The received complex baseband signal is represented by

\[
r(t)=\sum_{\ell=0}^{L-1}\alpha_\ell s(t-\tau_\ell)\exp(j2\pi\Delta f_\ell t)+n(t),
\]

where $L$ is the total number of modeled components and $\ell=0$ denotes the direct component. The direct-path delay $\tau_0$ is the delay reference, and Doppler offsets are referenced to the direct component so that $\Delta f_0=0$. Each component has complex gain $\alpha_\ell$, delay $\tau_\ell$, and relative Doppler offset $\Delta f_\ell$; the complex gain contains amplitude and phase. Thus, $L=1$ is a direct-only model, while $L=2$ contains the direct component and one secondary component.

### B. SAGE-Based Delay--Doppler Parameter Estimation

For a current path $\ell$ at iteration $i$, the implementation forms a hidden signal by subtracting the synthesized contributions of the other paths,

\[
r_\ell^{(i)}(t)=r(t)-\sum_{k\ne\ell}\hat{\alpha}_k^{(i)}q(t;\hat{\tau}_k^{(i)},\hat{\Delta f}_k^{(i)}),
\]

where $q(\cdot)$ is the code replica with fractional delay and Doppler. The selected path is refined using a normalized delay--Doppler correlation objective,

\[
(\hat{\tau}_\ell,\hat{\Delta f}_\ell)=\mathop{\arg\max}_{\tau,\Delta f}\frac{|q(\tau,\Delta f)^H r_\ell^{(i)}|^2}{q(\tau,\Delta f)^Hq(\tau,\Delta f)}.
\]

The implementation realizes the coarse grid correlation with FFT/IFFT operations and uses explicit fractional-delay replicas for local refinement. After path-wise refinement, all complex gains are updated by a least-squares solve over the current replica matrix. The iterations stop after at most 10 updates or when the relative residual-RSS change is below $10^{-6}$. The local SAGE delay grid is 0.1 sample (0.01 chip) with a 0.8-sample neighborhood, and the local Doppler grid spans $\pm30$ Hz at 5 Hz spacing around the tracking-referenced estimate.

### C. Navigation-Data-Aided Observation Formation

Channel-specific tracking and telemetry information provides synchronization and sample support. Decoded navigation data bits provide the PRN- and time-aligned known sequence used for navigation-bit wipe-off and construction of complete 40-ms observation windows, while PRN/channel association selects the intended stream. The resulting valid observation windows form the input set for subsequent candidate screening and estimation. At 10.23 MHz, the sampling/code relation is 10 samples per C/A chip.

### D. Candidate Screening and Local Model-Order Estimation

Candidate-window screening uses a main-Doppler search of $\pm125$ Hz at 25 Hz spacing, local correlation refinement, and a residual search constrained by the tracking-derived relative-Doppler bound. The screening reduces the windows entering the more expensive local SAGE fit. For each screened window, models with $L=1,2,3,4$ are evaluated using fractional delay--Doppler paths. Sequential order increases require a valid model, the higher-order model to reduce the BIC by at least 10, and an incremental RSS reduction of at least 0.002 percent. A higher-order model ($L\geq2$) indicates that additional signal components improve the local representation of the observation, while final path confirmation additionally requires temporal consistency and multi-snapshot joint validation.

### E. Temporal Consistency and Multi-Snapshot Path Confirmation

Temporal validation compares path delay, Doppler, and relative power over neighboring windows. A temporally consistent candidate is retained when it has a consecutive matching run of at least three windows within a radius of two, with tolerances of 1.5 samples, 40 Hz, and 10 dB, respectively. For final joint confirmation, a 100-ms interval centered on each temporally consistent candidate is partitioned into five contiguous 20-ms snapshots. Joint model selection uses the same sequential BIC reduction rule, and a higher-order model is retained only if it is favored in at least four of the five snapshots. Only a valid joint solution in which a secondary component satisfies the final joint-confirmation criteria is retained as a confirmed multipath path. Local high-order selections and temporally consistent candidates remain intermediate evidence.

Taking the direct component ($\ell=0$) as the reference, the excess delay of component $\ell$ is defined as $\Delta\tau_\ell=\tau_\ell-\tau_0$ and is expressed primarily in samples; values in chips are obtained by unit conversion. The relative Doppler ($\Delta f_\ell$) denotes the Doppler offset with respect to the direct component rather than the absolute carrier Doppler. For the joint estimate, relative power is computed from the mean path power over the five snapshots and normalized to the direct component. These quantities are subsequently used to characterize the confirmed propagation paths across the evaluated environments. A confirmed event denotes one jointly confirmed observation interval, which may contain one or more confirmed secondary paths.

## IV. Experimental Results

### A. Hierarchical Path Extraction Behavior

To characterize how candidate components converge through the processing chain, we summarize valid 40-ms observation windows, screened candidates, temporally consistent candidates, and final joint confirmations. Figure 3 includes three representative cases that retain confirmed multipath paths from the Reflective-Feature, Highway/Open, and Mountain/Valley environments (G05, G25, and G11, respectively). In contrast, in the Mountain/Valley G28 track, temporally consistent candidates were rejected during multi-snapshot joint confirmation, whereas in the Urban G18 track, no candidate remained as a confirmed multipath event after final joint confirmation. Thus, the examples include both confirmed-multipath retention and final non-confirmation; the environment-wise characterization is based on the aggregated confirmed paths summarized separately in Table II and Fig. 4.

Here, a measurement run denotes one separate raw-IQ recording session; multiple PRN tracks may be analyzed within one run, and paths are counted only after the joint-confirmation criterion.

| Environment | Measurement runs | Analyzed PRN tracks | Confirmed events | Confirmed paths |
|---|---:|---:|---:|---:|
| Urban | 4 | 4 | 7 | 7 |
| Mountain/Valley | 3 | 9 | 13 | 14 |
| Highway/Open | 2 | 2 | 2 | 2 |
| Reflective-Feature | 2 | 2 | 7 | 7 |

**Table II.** Measurement coverage and confirmed multipath paths.

### B. Representative SAGE-Extracted Multipath Case

Figure 2 shows a representative G25 measurement from the Highway/Open environment. The retained jointly confirmed path has an excess delay of 1.1 samples, relative Doppler of -4.72 Hz, and relative power of -7.85 dB; its observation time is approximately 60.54 s and the selected model order is $L=2$. The jointly confirmed direct and secondary components are resolved in the estimated delay--Doppler representation, with their relative power reported in Fig. 2.

**Figure 2.** Representative confirmed G25 path from the Highway/Open environment. The plot shows the direct and secondary components and their extracted excess delay, relative Doppler, and relative power.

**Figure 3.** Hierarchical candidate reduction from valid 40-ms observation windows through candidate screening, temporal consistency, multi-snapshot joint confirmation, and confirmed paths for three representative measurements. The figure illustrates confirmation behavior across the processing hierarchy.

### C. Descriptive Path-Level Observations Across Measurement Environments

Across 17 analyzed PRN tracks from 11 measurement runs, 12 tracks from 8 runs yielded 30 jointly confirmed multipath paths. Table II summarizes the complete analyzed coverage, including tracks with zero or non-confirmed outcomes. The comparison is descriptive at the path level over the analyzed runs. Across the confirmed path observations, excess delay ranges from 1.0 to 4.5 samples, relative Doppler from -78.552 to 49.664 Hz, and relative power from -19.773 to -0.894 dB. The observed median excess delays for Urban, Mountain/Valley, Highway/Open, and Reflective-Feature are 1.20, 1.10, 1.15, and 1.20 samples, respectively; the corresponding relative-Doppler medians are -3.820, -0.468, -7.715, and 31.540 Hz. Figure 4 displays these three path parameters and their within-environment medians.

**Figure 4.** Path characteristics across the evaluated measurement environments. The panels show excess delay, relative power, and relative Doppler for individual paths; labels give the sample count $n$ for each environment and horizontal bars give within-environment medians.

Urban measurements exhibit the widest observed excess-delay range, with a maximum excess delay of 4.5 samples. Mountain/Valley measurements exhibit a broad observed range of relative Doppler, indicating substantial variation among the resolved propagation components. The seven Reflective-Feature paths come from two measurement runs and vary in excess delay, relative power, and relative Doppler. The two Highway/Open observations occupy a comparatively compact observed delay and relative-Doppler range. The framework therefore enables path-level comparison of multipath characteristics across the evaluated measurement environments.

## V. Conclusion

This paper evaluated a real dynamic GPS L1 C/A raw-IQ measurement chain and a navigation-data-aided hierarchical SAGE framework for path-level multipath extraction. The estimator pairs path-wise delay--Doppler refinement with navigation-aligned observations, temporal consistency checks, and multi-snapshot joint confirmation. Across the recorded road scenarios, the chain resolved and compared confirmed multipath components in excess delay, relative Doppler, and relative power. Controlled injected-path recovery and native $L=1$ versus $L=2$ comparisons provide complementary evidence for estimator behavior while preserving the distinction between known injected truth and SAGE-derived native path estimates.

## References

The Markdown citation keys are synchronized with the LaTeX source.

[1] J. A. Fessler and A. O. Hero, “Space-Alternating Generalized Expectation-Maximization Algorithm,” *IEEE Transactions on Signal Processing*, vol. 42, no. 10, pp. 2664--2677, Oct. 1994, doi: 10.1109/78.324732.

[2] B. H. Fleury, M. Tschudin, R. Heddergott, D. Dahlhaus, and K. I. Pedersen, “Channel Parameter Estimation in Mobile Radio Environments Using the SAGE Algorithm,” *IEEE Journal on Selected Areas in Communications*, vol. 17, no. 3, pp. 434--450, Mar. 1999, doi: 10.1109/49.753729.

[3] B. Eissfeller and J. O. Winkel, “GPS Dynamic Multipath Analysis in Urban Areas,” in *Proceedings of the 9th International Technical Meeting of the Satellite Division of the Institute of Navigation (ION GPS 1996)*, Kansas City, MO, pp. 719--727, Sep. 1996.

[4] E. J. Mora-Castro, C. J. Carrascosa-Sanz, and G. Ortega, “Characterisation of the Multipath Effects on the GPS Pseudorange and Carrier Phase Measurements,” in *Proceedings of the 11th International Technical Meeting of the Satellite Division of the Institute of Navigation (ION GPS 1998)*, Nashville, TN, pp. 1065--1074, Sep. 1998.

[5] P. Xie, M. G. Petovello, and C. Basnayake, “Multipath Signal Assessment in the High Sensitivity Receivers for Vehicular Applications,” in *Proceedings of the 24th International Technical Meeting of the Satellite Division of the Institute of Navigation (ION GNSS 2011)*, Portland, OR, pp. 1764--1776, Sep. 2011.

[6] A. Beitler, A. Tollkuehn, D. Giustiniano, and L. Plattner, “CMCD: Multipath Detection for Mobile GNSS Receivers,” in *Proceedings of the 2015 International Technical Meeting of the Institute of Navigation*, Dana Point, CA, pp. 455--464, Jan. 2015.

[7] A. Bilich and K. M. Larson, “Mapping the GPS Multipath Environment Using the Signal-to-Noise Ratio (SNR),” *Radio Science*, vol. 42, no. 6, p. RS6003, 2007, doi: 10.1029/2007RS003652.

[8] C. Fernandez-Prades, J. Arribas, P. Closas, C. Aviles, and L. Esteve, “GNSS-SDR: An Open Source Tool for Researchers and Developers,” in *Proceedings of the 24th International Technical Meeting of the Satellite Division of the Institute of Navigation (ION GNSS 2011)*, Portland, OR, pp. 780--794, Sep. 2011.

[9] Navstar GPS Directorate, “IS-GPS-200N: Navstar GPS Space Segment/Navigation User Interfaces,” Interface Specification IS-GPS-200N, Revision N, Aug. 1, 2022. Available: https://www.gps.gov/sites/default/files/2025-07/IS-GPS-200N.pdf
