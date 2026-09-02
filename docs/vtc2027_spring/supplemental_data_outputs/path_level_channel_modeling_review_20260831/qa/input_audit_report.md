# Path-Level Modeling Input Audit

This audit records the read-only population contract for the isolated path-level modeling review.
The rows are retained or persistent path observations, not a complete CIR or a set of confirmed physical paths.

## Counts

- Primary population rows: 518
- Elevation-ready rows: 487
- Cell-ready rows: 487
- Missing-elevation rows excluded from cell models: 31
- Unique tracks: 236
- Environment-only run-window groups: 290
- Elevation-ready run-window groups: 279

## Environment-Elevation Counts

| Cell | Rows | Source scenes |
|---|---:|---:|
| Mountain/Valley/HIGH | 32 | 2 |
| Mountain/Valley/LOW | 22 | 3 |
| Mountain/Valley/MID | 117 | 3 |
| Urban/HIGH | 129 | 5 |
| Urban/LOW | 18 | 3 |
| Urban/MID | 169 | 5 |

## Modeling Fields

| Quantity | Field | Unit |
|---|---|---|
| delay | `excess_delay_samples` | samples relative to the direct-path reference |
| doppler_primary | `absolute_doppler_hz` | Hz, absolute relative Doppler |
| doppler_signed | `doppler_offset_hz` | Hz, signed relative Doppler |
| power | `relative_power_db` | dB relative to the direct-path reference |
| weight | `track_weight_recomputed_primary` | track-balanced analysis weight |

## Boundary

The current review can fit path-level delay-Doppler and path-relative-power distributions and derive a retained-path delay-dispersion ECDF.
It does not contain the full per-snapshot CIR needed for a complete PDP, received fading-envelope fit, full-channel RMS delay spread, or snapshot-lag correlation.
