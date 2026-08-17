# SAGE-Based High-Resolution Multipath Characterization of GPS L1 C/A Signals in Dynamic Vehicular Environments

## Abstract

Characterizing GNSS multipath from real vehicular raw-IQ measurements is difficult because reflected components evolve with motion while receiver-level indicators do not expose individual propagation paths. This paper evaluates a navigation-aided hierarchical SAGE framework for GPS L1 C/A raw-IQ measurements. Tracking and telemetry products, together with decoded navigation symbols, provide PRN/time alignment for NAV wiping and valid 40-ms observation-window construction, while PRN/channel association selects the intended stream. Candidate-window screening, fractional delay--Doppler SAGE estimation, temporal consistency validation, and multi-snapshot joint confirmation progressively refine the path set. The resulting confirmed observations expose excess delay, relative Doppler, and relative power at the path level. These measurements provide a basis for bounded descriptive comparison of multipath behavior across the evaluated dynamic vehicular environments.

**Keywords:** GNSS multipath; GPS L1 C/A; raw-IQ measurements; SAGE; delay--Doppler path extraction.

## I. Introduction

Global navigation satellite systems support vehicle navigation and intelligent transportation, but reflections in dynamic roadside environments make the received signal time-varying [@eissfeller1996gpsdynamic; @mora1998multipath; @beitler2015cmcd]. Buildings, terrain, vehicles, and other structures can introduce propagation components whose delay, Doppler, and power change as the antenna moves. Carrier-to-noise density or signal-to-noise ratio, pseudorange residuals, and positioning error are useful indicators of receiver-level degradation, but they do not directly expose the propagation components responsible for an observation [@bilich2007snr; @xie2011vehicular; @beitler2015cmcd].

Real dynamic raw-IQ measurements therefore create a need for path-level analysis that is both physically interpretable and conservative in its confirmation rule. The challenge is not only to fit a multi-component model at an individual window, but also to distinguish a correlation candidate from a temporally supported component and from a jointly confirmed path. Established high-resolution parameter extraction provides the link between measured GNSS signals and propagation observations [@fleury1999sage]. This paper applies that basis to a NAV-aided hierarchical workflow that combines candidate screening, temporal consistency, and multi-snapshot joint confirmation for traceable path observations.

This paper makes three contributions:

1. It establishes a real dynamic GPS L1 C/A raw-IQ measurement and processing basis using GNSS-SDR support products and navigation-aided observation construction.
2. It evaluates a NAV-aided hierarchical SAGE processing framework with progressive candidate screening, temporal consistency checking, and multi-snapshot joint confirmation.
3. It provides measurement-based environment-wise characterization of SAGE-extracted multipath path parameters across representative dynamic vehicular environments, focusing on excess delay, relative Doppler, and relative power.

## II. Measurement and Experimental Setup

### A. Measurement Platform

The measurement platform used a TEST-TREE RF-Catcher V2 RF signal capture and playback device together with a GNSS dome antenna. The antenna was right-hand circularly polarized (RHCP), had a documented active gain of 40 dB, and was mounted on the vehicle roof. The vehicle served as the dynamic antenna platform; vehicle type and vehicle performance were not treated as research variables.

Measurements from four representative dynamic environment classes were evaluated: Urban, Special Reflective, Highway/Open, and Mountain/Valley.

### B. Signal Acquisition Configuration

The measured signal was GPS L1 C/A at a documented center frequency of 1575.42 MHz [@gpsis200n2022]. Raw samples were stored as interleaved in-phase/quadrature (I/Q) data in little-endian signed 16-bit format. The measurements analyzed in this paper use a sampling rate of 10.23 MHz (10230000 Hz).

### C. Experimental Scenarios

The evaluated cases are:

- Urban;
- Special Reflective;
- Highway/Open;
- Mountain/Valley.

### D. Processing Overview

The overall measurement and processing framework is illustrated in Fig. 1. Tracking and telemetry products provide synchronization and sample support. Decoded navigation symbols provide PRN/time alignment for NAV wiping and construction of complete 40-ms observation windows, while PRN/channel association selects the intended stream. This preparation gives subsequent correlation and fractional delay--Doppler estimation a common known-symbol observation unit. The GNSS-SDR support chain follows the configurable software-defined GNSS receiver architecture described in [@fernandez2011gnsssdr].

**Table I.** The measurement and processing configuration is summarized in the LaTeX manuscript.

## III. NAV-aided Hierarchical SAGE Multipath Estimation

### A. Signal and Multipath Model

The estimator follows the space-alternating generalized expectation-maximization framework [@fessler1994sage] and its established use for high-resolution mobile-channel parameter estimation [@fleury1999sage]. The received complex baseband signal is represented by

\[
r(t)=s_0(t)+\sum_{\ell=1}^{L}\alpha_\ell s(t-\tau_\ell)\exp(j2\pi\Delta f_\ell t)+n(t),
\]

where $s_0(t)$ is the direct contribution and each additional component has complex gain $\alpha_\ell$, delay $\tau_\ell$, and Doppler offset $\Delta f_\ell$ relative to the direct component. The complex gain contains amplitude and phase.

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

### C. NAV-Aided Observation Formation

Channel-specific tracking and telemetry information provides synchronization and sample support. Decoded navigation symbols provide the PRN- and time-aligned symbol sequence used for NAV wiping and construction of complete 40-ms observation windows, while PRN/channel association selects the intended stream. The resulting valid observations are the mother set for subsequent estimation; this formation step does not assign a multipath label. At 10.23 MHz, the sampling/code relation is 10 samples per C/A chip.

### D. Candidate Screening and Local Model-Order Estimation

Candidate-window screening uses a main-Doppler search of $\pm125$ Hz at 25 Hz spacing, local correlation refinement, and a residual search constrained by the tracking-derived relative-Doppler bound. The screening reduces the windows entering the more expensive local SAGE fit. For each screened window, models with $L=1,2,3,4$ are evaluated using fractional delay--Doppler paths. Sequential order increases require a valid model, a BIC gain of at least 10, and an incremental RSS reduction of at least 0.002 percent. A higher-order model ($L\geq2$) indicates that additional signal components improve the local representation of the observation, while final path confirmation additionally requires temporal consistency and multi-snapshot joint validation.

### E. Temporal Consistency and Multi-Snapshot Path Confirmation

Temporal validation compares path delay, Doppler, and relative power over neighboring windows. A reliable center requires a consecutive matching run of at least three windows within a radius of two, with tolerances of 1.5 samples, 40 Hz, and 10 dB, respectively. Five contiguous 20-ms snapshots centered on a reliable window are then jointly estimated over approximately 100 ms. Joint model selection uses the same sequential BIC gain rule and requires at least four snapshot wins for a higher-order model. Only a valid joint solution containing a secondary path that satisfies the joint-confirmation path-table criterion enters the confirmed set. Local high-order selections and temporally reliable centers remain intermediate evidence.

Taking the direct component ($\ell=0$) as the reference, the excess delay of path $\ell$ is defined as $\Delta\tau_\ell=\tau_\ell-\tau_0$ and is expressed primarily in samples; values in chips are obtained by unit conversion. The relative Doppler ($\Delta f_\ell$) denotes the Doppler offset with respect to the direct component rather than the absolute carrier Doppler, while relative power is referenced to the direct component. These quantities are subsequently used to characterize the confirmed propagation paths across the evaluated environments.

## IV. Experimental Results

### A. Hierarchical Path Extraction Behavior

To characterize how candidate components converge through the processing chain, we summarize valid 40-ms observation windows, candidate windows, temporally consistent candidates, and final joint confirmations. Figure 3 presents the reduction for three representative cases. For each candidate window, local SAGE estimation evaluates model orders $L=1$--$4$; these evaluations therefore represent alternative model orders for the same window rather than an additional set of independent observations. In the reference-scene G28 track, a temporally consistent candidate is rejected by the subsequent multi-snapshot joint confirmation. In the G18 track from the F1023_V70_D0120_P1 scene, none of the candidates was retained as a confirmed multipath event after the final joint confirmation. These representative cases illustrate the behavior of the hierarchical confirmation procedure; the environment-wise characterization is based on the aggregated confirmed paths summarized separately in Table II and Fig. 4. The reduction reflects progressively stronger evidence from local representation to temporal consistency and multi-snapshot joint confirmation.

| Environment | Independent scenes | Analyzed PRN tracks | Confirmed events | Confirmed paths |
|---|---:|---:|---:|---:|
| Urban | 4 | 4 | 7 | 7 |
| Mountain/Valley | 3 | 9 | 13 | 14 |
| Highway/Open | 2 | 2 | 2 | 2 |
| Special Reflective | 2 | 2 | 7 | 7 |

**Table II.** Measurement Coverage and Confirmed Multipath Paths Across Dynamic Vehicular Environments. Paths are counted only after the joint-confirmation criterion.

### B. Representative SAGE-Extracted Multipath Case

Figure 2 shows a representative G25 measurement from the Highway/Open scenario. The retained jointly confirmed path has an excess delay of 1.1 samples (secondary delay 1.2 samples), relative Doppler of -4.7159 Hz, and relative power of -7.8526 dB; its observation time is approximately 60.5369 s and the selected model order is $L=2$. This example illustrates the separability of the direct and secondary propagation components after joint confirmation in delay, relative Doppler, and relative power.

**Figure 2.** Representative confirmed G25 path from the Highway/Open scenario. The plot shows the direct and secondary components and their extracted excess delay, relative Doppler, and relative power.

**Figure 3.** Hierarchical candidate reduction from valid 40-ms observation windows through candidate screening, temporal consistency, multi-snapshot joint confirmation, and confirmed paths for three representative measurements. The figure illustrates confirmation behavior across the processing hierarchy.

### C. Environment-Wise Path Characteristics

The confirmed path set contains 30 path observations from 12 path-bearing PRN tracks across 8 independent scenes; Table II summarizes the analyzed measurement coverage, including tracks with zero or non-confirmed outcomes. Across the confirmed path observations, excess delay ranges from 1.0 to 4.5 samples, signed relative Doppler from -78.552 to 49.664 Hz, and relative power from -19.773 to -0.894 dB. The observed median excess delays for Urban, Mountain/Valley, Highway/Open, and Special Reflective are 1.20, 1.10, 1.15, and 1.20 samples, respectively; the corresponding signed relative-Doppler medians are -3.820, -0.468, -7.715, and 31.540 Hz. Figure 4 displays these three common path parameters and their within-environment medians.

The observation spans derived from the first and last valid windows, summed across the analyzed tracks, are 177.38 s (Urban), 203.16 s (Mountain/Valley), 383.98 s (Highway/Open), and 150.50 s (Special Reflective). These durations provide the observation context for each environment. Because valid observation windows overlap, event counts are used to summarize the observed confirmed cases rather than as normalized occurrence-rate estimates.

**Figure 4.** Environment-wise characteristics of jointly confirmed paths. The panels show excess delay, relative power, and signed relative Doppler for individual paths; labels give the sample count $n$ for each environment and horizontal bars give within-environment medians.

### D. Cross-Environment Multipath Characteristics

Distinct multipath characteristics are observed across the evaluated vehicular environments. Urban measurements exhibit the widest observed excess-delay range, including a maximum excess delay of 4.5 samples, indicating reflected components with larger relative path-length differences in the current measurements. Mountain/Valley contributes the largest confirmed-path sample and a broad range of relative Doppler, consistent with richer time-varying propagation geometries under vehicle motion. Special Reflective contains confirmed paths in two independent scenes, with appreciable variation in excess delay, relative power, and relative Doppler consistent with localized strong-reflector conditions. The currently available Highway/Open paths are fewer and show a more compact observed delay and Doppler range. Overall, these measured differences are qualitatively consistent with the distinct reflection and scattering conditions associated with urban structures, mountainous terrain, open roads, and localized reflectors. The framework therefore resolves and characterizes environment-associated multipath behavior from dynamic vehicular measurements.

## V. Conclusion

This paper evaluated a real dynamic GPS L1 C/A raw-IQ measurement chain and a NAV-aided hierarchical SAGE framework for path-level multipath extraction. The estimator combines path-wise delay--Doppler refinement with navigation-aligned observations, temporal consistency, and multi-snapshot joint confirmation. The resulting evidence supports bounded comparison of measured excess delay, relative Doppler, and relative power across the evaluated vehicular environments. Future work will expand independent scene coverage and develop the path and channel-parameter databases required for broader statistical analysis.

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
