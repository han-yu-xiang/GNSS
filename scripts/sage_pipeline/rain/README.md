# Rain SAGE branch

This directory is the independent Rain Channel Emulation adapter. It is not
the formal nav_sage_v2 production pipeline.

## Current policy

- RAIN_SAGE_USE_SEPARATE_PIPELINE = YES
- Supported sample rate: 10.23 MHz only.
- NMEA, PVT, RINEX, trajectory, and geometry are not prerequisites for the
  Rain MVP.
- Elevation conditioning is disabled.
- A common PRN is preferred for matched weather validation but is not required
  for a per-recording pooled weather analysis.
- Raw IQ remains external under rain/; scene metadata points to it.
- Rain output must use scenes/<scene>/sage_results/rain_sage_v1/<PRN>/.
- new_only=true and Resume=false are mandatory.

## Implemented

- audit_rain_sage_inputs.py: standard-library static audit of source
  configuration, telemetry DAT records, mapped tracking files, raw metadata,
  and Rain MVP policy. It never opens .bin raw IQ.
- build_rain_stage0.m: Rain Stage0 adapter. It constructs the compatible
  symbol/window catalog from tracking MAT + telemetry DAT, uses explicit
  NaN/unavailable_no_NMEA for speed, and uses the existing fallback
  relative-Doppler bound. It does not read raw IQ.
- run_rain_sage_pipeline.m: shared-core Rain entry. Default invocation is
  preflight-only; full execution remains gated by independent production
  regression and Commander approval. Stage0Only=true is available only after
  separate approval.

## Stage1-Stage4 boundary

The production Stage1-Stage4 mathematics, extracted without intentional
parameter changes, are now in
scripts/sage_pipeline/core/run_sage_stage1_stage4_core.m. Both the formal
production entry and the Rain entry call that same function. The extraction is
intended as a no-semantic-change refactor; source/static checks pass, but
independent MATLAB and frozen artifact regression is still required before
Rain full execution is released.

## Static audit command

    D:/Research/ChannelModeling-Agent/.venv/Scripts/python.exe scripts/sage_pipeline/rain/audit_rain_sage_inputs.py --project-root E:/GNSS_Multipath_Project

## Future preflight call

    run_rain_sage_pipeline("F1023_clear", "G24", ...
        "TrackingChannel", 10, ...
        "ProjectRoot", "E:/GNSS_Multipath_Project", ...
        "Resume", false)

This call is currently preflight-only and does not launch MATLAB or SAGE.
