# Main-Path Common-Gain / Observable-Fade Model v1

## Status

`MAIN_PATH_COMMON_GAIN_FADE_MODEL = COMPLETED_WITH_LIMITATIONS`

`MODEL_IMPLEMENTATION = IMPLEMENTED`

`INDEPENDENT_QA = PASS_WITH_LIMITATIONS`

This is a bounded receiver-tracking modeling layer. It is not a calibrated RF-power model, a physical LOS decomposition, or the complete four-path darkroom generator.

## Scope and execution boundary

The build used the fixed Python environment `D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe` with Python 3.12.9, NumPy 2.5.1, SciPy 1.18.0 and OpenBLAS. It read existing GNSS-SDR tracking MAT fields through the project's read-only HDF5 reader and used verified time/geometry CSV provenance. It did not open raw IQ, invoke MATLAB, invoke SAGE, start a batch task, read Stage3/Stage4 outputs for selection, or process 20.46 MHz data.

The input contract retained the one G06 legacy run as excluded and resolved 63 environment-eligible runs. The current protected production pipeline hash remained `bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c`.

## Frozen model semantics

- For each run, `C_ref_run` is the median valid `LOCK_GOOD` tracking C/N0.
- `common_gain_db = CN0 - C_ref_run` and `common_gain_linear = 10^(common_gain_db/20)`.
- The local upper baseline is the same-segment 10 s centered 90th-percentile C/N0 envelope; segments shorter than 2 s are inconclusive.
- A fade enters at at least 3 dB depth for at least 20 ms and exits at at most 1 dB for at least 100 ms.
- `LOCK_BAD`, continuity gaps and record termination are represented as right-censored or inconclusive observations, not as exact zero amplitudes or exact maximum fade depths.
- Elevation is assigned only by same-scene, same-PRN nearest GSV observation within 5 s; there is no interpolation or scene-average substitution. The bins are `LOW=[0,30)`, `MID=[30,60)`, and `HIGH=[60,90]` degrees.
- Marginal fitting and family selection use deterministic scene-balanced/grouped processing. Normal gain candidates were Student-t, normal and Laplace; fade depth and duration candidates were lognormal, Gamma and Weibull.

The resulting selected families are Student-t for normal common gain, lognormal for observed fade depth, and Gamma for observed fade duration. These are empirical choices under the frozen grouped selection rule, not universal physical laws.

## Observed build output

| Quantity | Value |
|---|---:|
| Environment-eligible runs | 63 |
| Physical tracking inputs | 63 |
| Tracking records represented | 894,470 |
| Valid/inconclusive tracking records | 808,133 / 86,337 |
| Canonical 20 ms grid rows | 307,572 |
| Observable fade events | 91 |
| Right-censored fade events | 30 |
| Geometry-valid grid rows | 173,498 |
| Environment × elevation cells represented | 12 |

The model namespace is:

`dataset_generation_logs/channel_modeling/main_path_common_gain_fade_v1_20260826_r4/`

The final model manifest SHA-256 is `6f36dab892622c9b9dc61ecde91fda85ff12ca60eeea4f81fe37760f0acb1e45`. The independent QA result is `PASS_WITH_LIMITATIONS`; its result JSON SHA-256 is `cfee633b31287fb158af60c61c33ec0e5d69cd26e87bf229696673e66e41882`.

## Geometry and support limitations

All 12 environment/elevation cells have a gain record and explicit support status. The gain cells have sufficient direct grid rows for the implementation's grouped-support threshold. Fade-event support is much weaker: only Highway/Open has direct fade events in LOW/MID/HIGH (13/7/7 events); the other nine environment/elevation cells inherit their environment parent and are marked `PRIOR_ONLY` for fade events. Highway/Open MID/HIGH fade cells remain `SPARSE_PARTIAL_POOLING`.

Consequently, the output can support a conditional receiver-strength/fade diagnostic layer with explicit parent pooling, but it does not support strong independent fade-rate claims for every environment/elevation cell. A zero direct event count in a cell is a support statement, not a claim that the environment has no physical fading.

## Future-generator boundary

The output provides a common multiplicative gain interface for a future composition layer:

`RelativeAmplitude_0(t) = G_common(t)`

and, under an explicit future assumption,

`RelativeAmplitude_i(t) = G_common(t) × A_rel_i` for an activated NLOS path.

This build does not determine absolute RF power, phase, NLOS activation, path count, path lifetime, or the mapping from receiver lock loss to physical signal amplitude/recovery. The phase policy remains an external initial-phase plus Doppler-continuous-evolution assumption. The existing confirmed-NLOS path model and receiver lock-loss model remain separate layers.

## Provenance and retained attempts

The final r4 output is new-only. Earlier implementation-failure/diagnostic namespaces were not overwritten or deleted; the successful scientific output is identified by its own manifest and hashes. The final source hashes recorded in the manifest are:

| Source | SHA-256 |
|---|---|
| `main_path_gain_core.py` | `da831bf0591c3ff9e816a8b12a4d7cd08b0f23f124151ff7ad9298fcb7fbc484` |
| `build_main_path_common_gain_fade_model.py` | `0666a06c2f65f96adb7a9f2434d9f7071d896a6992261c15a53817c0f78a1da0` |
| frozen config | `5baeb0567baf6b24b018c923f50709375271c653d330e6f1888b0469befa9b77` |
| source preflight | `19bac6bcf580554c40666f0cf41a1edc87e827a30424c8d23d93a5139b402d88` |

The independent auditor is `scripts/analysis/channel_modeling/audit_main_path_common_gain_fade_model.py`; it checked output completeness, hashes, source contract, tracking/grid counts, censor semantics, geometry/cell coverage, parameter finiteness, temporal parameters and deterministic QA draws.

## Research status

This modeling layer is now implemented and independently QA-validated with explicit sparse-cell limitations. It is suitable as an input to the next separately authorized darkroom composition step. It does not by itself mean that the complete random four-path millisecond signal generator or a final statistical channel model has been completed.

```text
RAW_IQ_READ = NO
MATLAB_EXECUTED = NO
SAGE_EXECUTED = NO
BATCH_EXECUTED = NO
PROCESS_20_46_MHZ = NO
MODEL_QA = PASS_WITH_LIMITATIONS
NEXT_DECISION_REQUIRED = AUTHORIZE_OR_HOLD_DARKROOM_COMPOSITION_INTEGRATION
```
