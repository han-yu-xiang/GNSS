# VTC2027-Spring manuscript evidence package

Package ID: `vtc_evidence_package`  
Status: **Prepared / frozen-source extraction**  
Extraction date: **2026-08-15**  
Production state at extraction: `VTC_PRODUCTION_STATUS = FROZEN`

## Scope

This package contains paper-facing CSV extracts from already QA-passed evidence. It does not copy raw IQ, SAGE output directories, MATLAB output, or execution artifacts. No MATLAB, SAGE, raw-IQ processing, production task, statistical fitting, or channel-model computation was performed for this package.

The package covers T1-1 G05, T1-2 G25, T1-3 G11, and the QA-passed G18 zero-event control case. The five confirmed paths in the current T1 evidence are retained as path-level descriptive evidence. `G18` is included as a valid zero-event case under the fixed Stage4 criterion; it is not interpreted as physical absence of multipath.

## Directory contents

| Path | Purpose | Status |
|---|---|---|
| `manuscript_tables/measurement_configuration.csv` | Measurement and processing configuration table source | Prepared |
| `manuscript_tables/experimental_evidence_summary.csv` | One-row-per-task evidence summary | Prepared |
| `manuscript_figures/representative_path_case.csv` | Representative and alternate confirmed-path candidates | Prepared |
| `manuscript_figures/hierarchical_filtering_summary.csv` | Stage0-to-Stage4 funnel data | Prepared |
| `manuscript_figures/path_characterization.csv` | Five confirmed path rows for bounded descriptive plots/tables | Prepared |
| `extracted_data/README.md` | Scope marker for additional paper-facing extracts | Prepared; no extra extract required |

## Source ledger and extraction rules

### `measurement_configuration.csv`

Sources:

- `E:/GNSS_Multipath_Project/docs/paper_draft/sections/04_Experimental_Setup.md`
- `E:/GNSS_Multipath_Project/docs/GNSS_SAGE_PAPER_HANDOFF_CURRENT.md`
- the RF-Catcher documentation statement cited by the Experimental Setup draft

The row reproduces documented facts only: TEST-TREE RF-Catcher V2, GNSS dome antenna, RHCP, 40 dB active gain documented in the source narrative, roof mounting, GPS L1 C/A at 1575.42 MHz, 10.23 MHz/10230000 Hz, interleaved little-endian int16 IQ, and the documented GNSS-SDR plus NAV-aided SAGE processing chain. The requested table does not infer vehicle model, antenna model, time synchronization, IF frequency, or undocumented clock details.

A standalone RF-Catcher manual file was not present in the project file listing at extraction time; the package therefore cites the existing project documentation rather than inventing a manual path.

The package state and freeze decision were also checked against `E:/GNSS_Multipath_Project/docs/vtc2027_spring/VTC_PLAN.md`, `E:/GNSS_Multipath_Project/docs/vtc2027_spring/EVIDENCE_MATRIX.md`, and `E:/GNSS_Multipath_Project/docs/vtc2027_spring/VTC_PRODUCTION_PRIORITY_QUEUE.md`. The G12 QA report was reviewed as supplemental background and is not silently added to the four-row frozen task summary.

### `experimental_evidence_summary.csv`

Primary source:

- `E:/GNSS_Multipath_Project/docs/vtc2027_spring/evidence/vtc_evidence_summary.csv`

The task rows and counts are cross-checked against:

- `E:/GNSS_Multipath_Project/docs/10MHz_FULL_SAGE_PRODUCTION_T1_1_G05_QA_REPORT.md`
- `E:/GNSS_Multipath_Project/docs/10MHz_FULL_SAGE_PRODUCTION_T1_2_G25_QA_REPORT.md`
- `E:/GNSS_Multipath_Project/docs/10MHz_FULL_SAGE_PRODUCTION_T1_3_G11_QA_REPORT.md`
- `E:/GNSS_Multipath_Project/docs/10MHz_FULL_SAGE_PRODUCTION_A2_G18_QA_REPORT.md`

`geometry_context` is deliberately limited to scene/PRN planning context. It is not an event-level elevation label. The existing geometry QA is `PARTIAL`, so this table must not be used to claim geometry-complete LOW/MID/HIGH statistics.

### `representative_path_case.csv`

Primary source:

- `E:/GNSS_Multipath_Project/docs/vtc2027_spring/evidence/vtc_confirmed_path_database.csv`

The Stage4 path artifacts named in each row are retained as traceability references. G25 window 985 is the primary candidate because its task passed independent QA, its Stage4 path has complete finite path parameters, and it gives a clear direct/secondary path representation. The source event/joint-model maximum-coherence value is not used for this figure-selection decision or displayed as a path parameter.

The alternatives retained in the same CSV are G05 windows 493 and 495, G25 window 970, and G11 window 1264. The direct Stage1 correlation/detection metric is not stored in the Stage4 path artifact, so `correlation_or_detection_metric` is explicitly `NA`; it is not reconstructed from another stage.

### `hierarchical_filtering_summary.csv`

Sources are the four task QA reports listed above. `Stage0_count` is the complete 40 ms-window count, `Stage1_selected` is the selected Stage1 candidate-window count, `Stage2_evaluations` is the model-order evaluation-row count, and the later columns are the QA-reported Stage3/Stage4 and confirmed counts. Stage2 high-order selections and Stage3 reliable centers are intermediate evidence; only the Stage4 criterion admits confirmed events/paths.

### `path_characterization.csv`

Source:

- `E:/GNSS_Multipath_Project/docs/vtc2027_spring/evidence/vtc_confirmed_path_database.csv`

Only Stage4-confirmed path rows are included. The file contains path-level delay, excess delay, relative power and relative Doppler fields. Any retained `source_event_maximum_coherence` field is explicitly event/joint-model provenance, not a path-level parameter. It intentionally contains no event elevation, azimuth, SNR, or geometry statistics because event-level geometry alignment remains `PARTIAL`.

## Fixed confirmation and scientific boundaries

The extraction uses the project criterion:

```text
joint_valid = 1
AND joint_multipath_count > 0
AND a matching Stage4 path row has is_multipath = 1
```

The package permits bounded descriptive statistics, empirical comparisons, and environment grouping. It does not generate RMS delay spread, K-factor, PDP models, stochastic fits, multipath probability models, or any other statistical channel model. Five paths are not sufficient evidence for a universal propagation law. The package also does not claim that the complete event database or the complete 10.23 MHz production dataset exists.

## Geometry limitation

The existing `E:/GNSS_Multipath_Project/docs/vtc2027_spring/evidence/vtc_geometry_alignment_qa.md` reports `PARTIAL` alignment for the five T1 path rows. The candidate NMEA/GSV values remain diagnostic provenance only. No event-level LOW/MID/HIGH statistical claim is released by this package.

## Paper-use status

- Table I source: **READY**
- Table II source: **READY**
- Figure 1: **READY / EXISTING** from the VTC workflow asset; this package does not duplicate the figure source.
- Figure 2: **READY** as candidate data; final visual design remains a manuscript task.
- Figure 3: **READY** as hierarchical funnel data; final visual design remains a manuscript task.
- Figure 4: **READY** for path-level descriptive characterization only; geometry-conditioned interpretation is not ready.

`NEXT_VTC_DECISION_REQUIRED = YES`

The next decision belongs to the Commander: select bounded manuscript claims and figure/table usage from this frozen evidence package. No new production request is implied by this package.
