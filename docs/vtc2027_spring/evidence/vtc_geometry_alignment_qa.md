# VTC Event-Level Geometry and Time-Alignment QA

Date: 2026-08-15  
Scope: existing VTC Tier-1 production evidence only; no new SAGE production was executed.

## QA decision

`geometry_alignment_status = PARTIAL`

Five confirmed path rows from T1-1, T1-2 and T1-3 have reproducible **provisional** nearest-row matches to the existing NMEA/GSV satellite-geometry time series. No event is promoted to `COMPLETE` geometry evidence because the current production provenance does not freeze the full observation-time bridge used by this diagnostic. The values below must not be used as geometry-complete LOW/MID/HIGH denominators or as a claim of event-level elevation dependence.

## Inputs and provenance

For each confirmed path, the diagnostic read only:

1. Stage4 `stage4_joint_summary.csv` for the confirmed event time and the event/joint-model `maximum_coherence` diagnostic.
2. Stage4 `stage4_joint_paths.csv` for the confirmed path parameters.
3. Stage0 `stage0_valid_40ms_windows.csv` for `window_id` and `tow_s`.
4. The scene RINEX NAV file for the calendar date of the available navigation epoch.
5. The existing `*_satellite_elevation_timeseries.csv`, generated from NMEA GSV.

The existing scene metadata records `geometry_source=NMEA_GSV`, `broadcast_ephemeris_position_recomputation=false`, and `rinex_nav_usage=GPS_PRN_filter_only`. No satellite position was recomputed in this QA.

## Diagnostic join rule

The diagnostic converted the Stage0 GPS TOW to a UTC candidate using the RINEX navigation calendar context and the standard GPS--UTC offset of 18 s, then selected the nearest existing GSV timestamp for the same PRN. No interpolation or scene/PRN mean elevation was used. This is an audit diagnostic, not a change to the production geometry generator.

The 18 s conversion constant and the relationship between the SAGE observation clock and the NMEA/RINEX clock are not recorded as a frozen project execution-provenance field. Therefore a nearest-row match is reported as `PARTIAL`, even when the numerical timestamp distance is small.

## Event-level diagnostic results

| Event | Window | Stage0 TOW (s) | Candidate UTC | Nearest GSV UTC | |Δt| (s) | Elevation (deg) | Azimuth (deg) | SNR (dB-Hz) | Candidate group | Status |
|---|---:|---:|---|---|---:|---:|---:|---:|---|---|
| T1-1_G05_W493 | 493 | 228957.84 | 2026-01-20 15:35:39.840 | 2026-01-20 15:35:40.000 | 0.16 | 20 | 41 | 44 | Low | PARTIAL |
| T1-1_G05_W495 | 495 | 228957.88 | 2026-01-20 15:35:39.880 | 2026-01-20 15:35:40.000 | 0.12 | 20 | 41 | 44 | Low | PARTIAL |
| T1-2_G25_W985 | 985 | 564085.68 | 2026-01-17 12:41:07.680 | 2026-01-17 12:41:07.990 | 0.31 | 79 | 65 | 49 | High | PARTIAL |
| T1-2_G25_W970 | 970 | 564085.38 | 2026-01-17 12:41:07.380 | 2026-01-17 12:41:06.990 | 0.39 | 79 | 65 | 48 | High | PARTIAL |
| T1-3_G11_W1264 | 1264 | 563869.30 | 2026-01-17 12:37:31.300 | 2026-01-17 12:37:30.990 | 0.31 | 35 | 69 | 42 | Mid | PARTIAL |

These candidate values are copied from the nearest existing GSV rows and are retained in `vtc_confirmed_path_database.csv` with explicit `geometry_candidate_*` names. They are not approved event-level geometry fields.

## Why the result is not COMPLETE

- The run context provides recording time, TOW and NMEA/geometry file paths, but does not provide a validated absolute observation-clock origin tying every SAGE window to the NMEA UTC epoch.
- The current geometry metadata explicitly says that RINEX NAV is used for PRN filtering, not broadcast-ephemeris position recomputation.
- The GPS--UTC conversion used for this diagnostic is not recorded in the existing execution receipt or geometry-generation provenance.
- The existing geometry is NMEA/GSV elevation/azimuth/SNR; satellite ECEF position and an independently verified event-time interpolation/clock model are absent.

Consequently, `COMPLETE=0/5`, `PARTIAL=5/5`, and no event is eligible for a geometry-complete elevation-bin statistic. The scene-level planning labels LOW/MID/HIGH remain metadata context only.

## Missing evidence

1. A frozen and independently verified TOW-to-UTC/observation-clock bridge for the SAGE windows.
2. Provenance for the GPS--UTC offset and the applicable GPS week/epoch mapping in the production run receipt.
3. If required by the paper claim, satellite position/azimuth/elevation recomputation or an independently validated event-time geometry product.

No interpolation, mean-elevation substitution, or scene-label substitution was used to fill these missing fields.

## Consequence for VTC claims

The existing confirmed path database supports measurement-based path characterization and candidate geometry diagnostics. It does not yet support a geometry-QA-complete LOW/MID/HIGH event-level comparison. The current evidence stop remains in force; this report does not authorize T1-4/T1-5 or any additional SAGE production.
