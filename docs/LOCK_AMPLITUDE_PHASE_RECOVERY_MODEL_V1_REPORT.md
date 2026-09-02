# Lock-State Amplitude, Phase, and Recovery Model v1

## Status

`COMPLETED_WITH_LIMITATIONS / IMPLEMENTED / INDEPENDENT_QA_PASS_WITH_LIMITATIONS`

This report records the offline implementation of the receiver lock-state to
amplitude, phase, and recovery composition layer. It is a bounded simulation
layer built from frozen project artifacts. It is not a complete statistical
channel model, an absolute-RF-power calibration, a physical receiver
sensitivity model, or a runnable four-path darkroom generator.

The final immutable build is in:

`dataset_generation_logs/channel_modeling/lock_amplitude_phase_recovery_v1_20260826_r3/`

The earlier r1 partial build and r2 build/QA failure remain in their own
namespaces and were not deleted, overwritten, resumed, or silently repaired.

## Scope and execution boundary

The implementation used only existing derived CSV/CSV.GZ/JSON artifacts. It did
not read raw IQ, run MATLAB, run SAGE, start a batch task, process 20.46 MHz,
or modify `scenes/**/sage_results`, the production pipeline, metadata,
inventory, or parent model artifacts.

The protected production entry remained unchanged:

`scripts/sage_pipeline/run_nav_sage_pipeline.m`

SHA-256:
`bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c`

## Frozen provenance

The retry3 configuration is
`configs/channel_modeling/lock_amplitude_phase_recovery_v1_retry3.json`.
Its SHA-256 is
`5d4230149629e77d0f77a54197a32361dfa877e87ad8980fa7274d89a3ba3efc`.

The build and independent audit sources are:

| Object | Path | SHA-256 |
|---|---|---|
| Core semantics | `scripts/analysis/channel_modeling/lock_amplitude_phase_recovery_core.py` | `29e85c4e40f4c30b2551f2a548b520b9f9004b1ac1d68218b576d6fd1563c4ac` |
| Offline builder | `scripts/analysis/channel_modeling/build_lock_amplitude_phase_recovery_model.py` | `2e7c8ff968411f8c645181bbc5fb7bc45f7bf57f598696c947fba60fed046af2` |
| Independent auditor | `scripts/analysis/channel_modeling/audit_lock_amplitude_phase_recovery_model.py` | `7c4e26cd9f5030669cbadcb3eb5fa2655bea6c9df4ea8263ce676f66b54522fd` |
| Retry3 configuration | `configs/channel_modeling/lock_amplitude_phase_recovery_v1_retry3.json` | `5d4230149629e77d0f77a54197a32361dfa877e87ad8980fa7274d89a3ba3efc` |
| Protected production entry | `scripts/sage_pipeline/run_nav_sage_pipeline.m` | `bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c` |

Parent source hashes are recorded in `source_preflight.csv`,
`model_manifest.json`, and `build_receipt.json`. The independent audit
reported `source_provenance_gate=PASS`, `namespace_and_hash_gate=PASS`, and
`protected_pipeline_gate=PASS`.

## Implemented composition semantics

### Receiver lock state

The state machine is:

`TRACKED -> FADING_TO_LOCK_BAD -> LOCK_BAD_HOLD -> RECOVERING -> TRACKED`

with `INCONCLUSIVE` reserved for missing or invalid evidence. The frozen
tracking diagnostic uses `carrier_lock_test < -0.5`, a 20 ms bad-lock debounce,
and 100 ms good-lock stability for reacquisition. Time is derived from the
tracking sample counter at 10.23 MHz. Continuity gaps are not bridged and do
not become outages; terminal records remain right-censored where appropriate.
Lock timing is conditioned on `environment_class` only. Elevation is not used
to invent an elevation-conditioned lock law.

### Common gain and lock envelope

The parent common-gain quantity is a run-normalized tracking C/N0 proxy, not
absolute RF power. The relative amplitude conversion is:

`common_gain_linear = 10^(common_gain_db / 20)`

The composition contract applies a shared real envelope to path 0 and all
active NLOS slots:

`A_i[m] = G_background[m] * G_lock[m] * Z_i * A_rel_i`

Consequently, a lock envelope changes the common scale while preserving the
relative NLOS ratios within a block. An active NLOS relative amplitude may be
greater than one. Path 0 is a simulation reference slot and is not asserted to
be physical LOS or to be the strongest path.

The default mode is `EMPIRICAL_DIAGNOSTIC_PROXY`, based on the observable fade
parent. It does not claim that the receiver physically loses lock at the
generated amplitude. The optional `FORCED_LOCK_LOSS_STRESS` mode requires an
explicit positive user floor and is marked as an external stress assumption;
the build does not infer that floor from the tracking labels.

The envelope uses a raised-cosine entry/recovery shape and a positive numerical
floor of `1e-12` in the scientific composition mode. Exact zero is not the
default physical interpretation.

### Recovery duration and shape

Recovery is defined as returning within 1 dB of the pre-entry baseline for a
100 ms stability condition after the lock interval. The duration candidate
families are lognormal, Gamma, and Weibull; the frozen selection is Gamma under
the parent model's deterministic selection policy. The recovery shape
comparison uses per-trace min--max normalization before RMSE comparison, so a
constant dB translation cannot change the selected temporal shape. The selected
shape in this build is `raised_cosine`.

Support is explicit rather than silently expanded:

- Mountain/Valley has direct grouped support (`11` observed recovery rows,
  `2` scenes) in the generated parameter table.
- Urban, Special Reflective, and Highway/Open use the global parent under
  `PARTIAL_POOLING` in this build because the direct support gate is not met.
- A missing baseline, continuity gap, or record ending does not become a
  fabricated recovery duration.

### Phase

Phase is not fitted from the current artifacts. The frozen composition
assumption is an initial `Uniform(-pi, pi)` phase followed by 1 ms Doppler
continuous evolution:

`phi_next = wrap_to_pi(phi + 2*pi*relative_doppler_hz*0.001)`

Neither lock loss nor recovery resets the path phase in v1. Receiver
reacquisition phase reset is not modeled. This must remain labeled as an
external assumption in any generator or paper use.

### NLOS slots and missingness

The parent three-slot model supplies the fixed NLOS composition. Inactive slots
have amplitude `0` and delay/Doppler/phase `null`; null is not replaced by a
numeric zero. Active slots share the lock envelope but retain their sampled
path-level relative parameters. The block policy keeps base delay, Doppler,
and relative amplitude fixed within a block while phase and envelope evolve at
1 ms resolution.

## Build accounting

The final retry3 build receipt reports:

| Quantity | Value |
|---|---:|
| Environment-eligible lock events | 48 |
| Parent common-gain grid rows read | 307,572 |
| Recovery trace rows | 3,249 |
| Deterministic scalar draws | 16,384 (4,096 per environment) |
| Deterministic state sequences | 256 (64 per environment) |
| Build elapsed time | 8.08997 s |

The feature status accounting is 19 observed recoveries, 15 right-censored
recoveries, 11 inconclusive-gap cases, and 3 no-valid-baseline cases. All 48
features retain explicit status fields; no invalid case was silently converted
to a physical outage or LOS condition. The independent QA found 4 environment
parameter rows and zero fixed-duration fallback rows in the final artifact.

The final model manifest SHA-256 is:

`9eb1847eac27618f80475ceafe62616285a346c5da847afdb0e8f2c5fc63a3ee`

The final build receipt is
`dataset_generation_logs/channel_modeling/lock_amplitude_phase_recovery_v1_20260826_r3/build_receipt.json`.

## Independent QA result

QA artifact:
`dataset_generation_logs/channel_modeling/lock_amplitude_phase_recovery_v1_20260826_r3/independent_qa_result.json`

QA report:
`dataset_generation_logs/channel_modeling/lock_amplitude_phase_recovery_v1_20260826_r3/independent_qa_report.md`

All published gates passed:

`source_provenance`, `lock_gain_alignment`, `lock_timing`,
`amplitude_mapping`, `recovery_envelope`, `phase_continuity`,
`inactive_slot_semantics`, `determinism`, `namespace_and_hash`, and
`protected_pipeline`.

The final status is:

```text
MODEL_QA = PASS_WITH_LIMITATIONS
READY_FOR_GENERATOR_INTEGRATION = YES
HARDWARE_LOCK_LOSS_CALIBRATED = NO
ABSOLUTE_RF_POWER_CALIBRATED = NO
PHASE_DATA_FITTED = NO
COMPLETE_STATISTICAL_CHANNEL_MODEL = NO
DARKROOM_FOUR_PATH_GENERATOR = NOT_STARTED
```

## Interpretation boundary and next work

This layer can now be supplied to a separate darkroom generator composition
interface as a versioned, auditable receiver-diagnostic envelope, relative
path-amplitude mapping, recovery-duration model, phase assumption, and fixed
NLOS-slot contract. It cannot by itself establish:

- a physical probability of receiver loss of lock;
- a calibrated absolute main-path power or receiver sensitivity;
- a physical LOS/non-LOS label from `LOCK_BAD`;
- a fitted phase distribution;
- a path occurrence, path-lifetime, or inter-block persistence model;
- a complete four-path millisecond output generator; or
- a final statistical channel model.

The next authorized engineering step is a separate generator-composition
interface design and validation using this immutable r3 namespace. Any forced
lock-loss stress use must first receive an explicit user-supplied positive
floor and remain labeled `ASSUMPTION_ONLY`. No raw/MATLAB/SAGE/production task
is implied by this report.

