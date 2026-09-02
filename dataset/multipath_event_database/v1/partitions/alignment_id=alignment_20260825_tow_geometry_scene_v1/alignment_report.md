# Modeling context alignment — alignment_20260825_tow_geometry_scene_v1

## Result

`MODELING_CONTEXT_ALIGNMENT = COMPLETED_WITH_EXCLUSIONS`

The source audit partition remains immutable. This versioned overlay uses the
existing Stage0 TOW, NMEA/GSV UTC geometry, RINEX calendar date, the frozen
18-second GPS–UTC offset, and the existing validated human scene metadata.

## Counts

- Runs: `64`; scene context verified: `13/13`.
- Time alignment verified: `13/13`.
- Event contexts: `308`; event-time geometry valid: `284`.
- Confirmed events/paths: `96/104`.
- Environment-ready confirmed paths (G06 excluded): `100`.
- Elevation-ready confirmed paths (same-PRN nearest GSV within 5s): `84`.

## Exclusions

- G06 legacy: retained in the source audit and excluded from both modeling inputs.
- Missing requested PRN in geometry: retained with null event geometry.
- Nearest geometry farther than the fixed tolerance: retained with null event geometry.

No interpolation, scene mean, or filename-derived geometry was used.

## Execution record

- Raw IQ read: no
- MATLAB/SAGE/batch started: no
- Existing SAGE artifacts, requests, manifest, inventory and metadata modified: no
- Channel parameters/statistical model started: no
