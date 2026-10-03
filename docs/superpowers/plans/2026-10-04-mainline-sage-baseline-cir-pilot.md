# Mainline SAGE Baseline and CIR Pilot Plan

## Scope

Run and validate only `F1023_V70_D0117_P2 / G28 / ch1`. Keep the frozen SAGE entry point byte-for-byte unchanged. Do not run the remaining 88 tasks, other scenes, or 20.46 MHz data. Preserve all pre-existing working-tree changes and archive contents. Do not commit or push.

Approved frozen source SHA-256:

`bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c`

## Implementation and execution sequence

1. **Reconfirm preconditions.** Record the actual Git branch and dirty status without changing either. Rehash the frozen MATLAB source and stop on mismatch. Validate the exact manifest row and its metadata/input paths for this scene/PRN/channel, `sample_rate_hz=10230000`, `mapping_warning=NONE`, and `resume=false`; do not infer a channel. Confirm both the legacy transient staging directory and final `rerun_20261003_frozen_v3/G28_ch1` destination are absent. Locate and inventory the archived G28/ch1 baseline read-only. Confirm the MATLAB execution session is the project's approved normal-user PowerShell 7 environment. Do not read any raw IQ before this single-task execution.

2. **Add and validate the external single-task wrapper.** Add `scripts/sage_pipeline/Invoke-FrozenSageRerunSingle.ps1`; leave `run_nav_sage_pipeline.m` untouched. Test preflight rejection for hash mismatch, missing inputs, wrong manifest row, and either output collision. Test that execution passes the exact scene, PRN 28, channel 1, and `Resume=false`; accepts completion only when MATLAB exits successfully and Stage0–Stage4 artifacts are present; relocates only the produced `nav_sage_v2/G28` directory with same-volume `Move-Item`; refuses overwrite; and writes a receipt with source/destination paths, UTC times, file counts, byte counts, frozen source hash, and relocation status. Never edit `run_context`.

3. **Run exactly one frozen baseline task.** After all preflight checks pass, invoke the frozen entry point once from the approved normal-user environment. This authorizes raw-IQ access only for `F1023_V70_D0117_P2`. Record Stage0 valid NAV symbols/windows; Stage1 fast-scan and valid scan counts; Stage2 evaluated candidates, L=1..4 outputs, selected windows/paths; Stage3 persistence rows/reliable centers; and Stage4 joint summary/paths/counts. If execution or artifact validation fails, do not relocate an incomplete result and stop with the failure documented. Rehash the frozen source after execution.

4. **Perform strict read-only regression comparison.** Compare new Stage1–Stage4 products against the archived G28/ch1 baseline: schemas and column order, row counts, model order, selected windows and path identity, delay/Doppler/relative-power fields, Stage3 persistence and reliable centers, Stage4 validity/counts, event/path counts, and numeric values. Do not introduce tolerances. Report every nonzero difference and per-field maximum absolute difference. Any structural, path-selection, event, or other nonzero difference is not `PASS_EXACT`; stop before CIR, alpha extraction, and ledger generation. Continue only on exact equality.

5. **Add external CIR and complex-alpha sidecars.** After `PASS_EXACT`, add `scripts/channel_modeling/export_gnss_code_domain_cir.m` and a read-only Stage2 alpha extractor. Derive the raw-sample delay grid from `default_sage_configuration` (expected -5 through 40 samples at this sample rate); produce 1 ms complex CIR snapshots from only the authorized scene using DC removal, NAV wipe, and tracking-reference carrier/code wipe, without per-snapshot RMS normalization. Store `/time_s`, `/delay_samples`, `/cir_real`, `/cir_imag`, `/raw_iq_rms`, `/tracking_doppler_hz`, `/code_frequency_hz`, `/cn0_db_hz`, and `/nav_symbol` in `G28_ch1_code_domain_cir.h5`, with required provenance and `amplitude_reference_status=UNKNOWN_RECEIVER_GAIN_OR_AGC` when acquisition metadata provides no calibration evidence, in a metadata JSON beside the relocated result. Produce Stage0-window-aligned 40 ms PDP as the mean of 40 one-ms CIR powers, not a coherent complex sum. Preserve Stage2 complex alpha in `SAGE_COMPLEX_PATH_COEFFICIENTS.csv` without changing frozen Stage CSV/MAT schemas, and mark `SAGE_ALPHA_IS_FROM_WINDOW_NORMALIZED_IQ=YES`.

6. **Build the complete Stage2-based modeling ledger.** Keep one ledger row for every Stage2 selected-path row; require `LEDGER_STAGE2_SELECTED_PATH_ROWS = DIRECT_PATH_ROWS + MULTIPATH_ROWS`. Retain every `is_multipath=0` row as `modeling_class=DIRECT_PATH`, `primary_modeling_pool=NO`; set its Stage3/Stage4 flags to `NA` when those multipath-oriented tables do not map directly. For `is_multipath=1`, classify only by deterministic Stage3/Stage4 identity mappings: Stage2-only as `TRANSIENT_MPC` / `NO`; Stage3 persistent without Stage4 confirmation as `PERSISTENT_MPC` / `YES`; Stage3 persistent with Stage4 confirmation as `HIGH_CONFIDENCE_MPC` / `YES`. Stage4 is a validation label, not a hard gate. Do not use nearest-neighbor thresholds. If Stage4 mapping is ambiguous, set `stage4_confirmed=UNMAPPED`, preserve Stage4 outputs, and retain the Stage3-based class/pool. If a Stage3 ambiguity prevents determining transient versus persistent for any multipath row, do not guess or finalize the affected classification/counts; report it for direction.

7. **Validate outputs and stop.** Check CIR snapshot count is positive, time is monotonic, delay grid is fixed, complex values and raw RMS are finite, raw RMS is positive, and 40 ms PDP windows align one-to-one with Stage0 windows. Perform only the requested consistency comparison of primary SAGE delays and dominant CIR/PDP correlation peaks; do not add empirical pass thresholds. Validate alpha fields and provenance; check all four ledger classes, direct-path exclusion from MPC/pool counts, and exact row-count conservation. Write the requested reports (`MAINLINE_SAGE_BASELINE_RERUN_20261003.md`, `MAINLINE_SAGE_BASELINE_RERUN_COMPARISON.csv`, `BASELINE_CIR_EXPORT_AUDIT.md`, and `MPC_MODELING_LEDGER.csv`) and sidecars (`G28_ch1_code_domain_cir.h5`, its metadata JSON, and `SAGE_COMPLEX_PATH_COEFFICIENTS.csv`), plus the wrapper, exporter, tests, and relocation receipt. Stop after this one-scene pilot; do not schedule or launch further work.

## Stop conditions

- Frozen source hash mismatch or any post-run hash change.
- Missing/wrong manifest inputs, wrong sample rate/channel, or either output path already existing.
- Execution outside the approved normal-user environment, unsuccessful MATLAB exit, or incomplete Stage0–Stage4 outputs.
- Any nonzero baseline regression difference: report the complete comparison and do not perform CIR/alpha/ledger work.
- Stage3 ambiguity that prevents transient/persistent classification: do not guess; stop ledger finalization and report the affected rows. Stage4-only ambiguity does not block Stage3-based classification; preserve `stage4_confirmed=UNMAPPED` and report it.
- Any destination collision, unexpected output, or attempt to touch unrelated user changes or archived data.

## Explicitly out of scope

The remaining 88 tasks; other raw-IQ files/scenes; 20.46 MHz adaptation; SAGE algorithm/threshold changes; modifications to frozen outputs or archived baselines; physical deletion; commit/push; and editing `run_context`.
