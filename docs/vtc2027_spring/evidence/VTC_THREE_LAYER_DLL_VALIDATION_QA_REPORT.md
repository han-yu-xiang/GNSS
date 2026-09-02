# VTC Three-Layer and DLL Validation QA Report

- QA time (UTC): `2026-08-23T12:04:45.843286+00:00`
- Scope: Layer 1 controlled recovery, Layer 2 multipath stress, Layer 3 native model support, DLL code-bias case study
- Production namespace modified: `NO`
- Manuscript modified: `NO`

## Independent verdicts

- `LAYER1_CONTROLLED_QA`: **BLOCKED**
  - {"error": "missing experiment output: E:\\GNSS_Multipath_Project\\docs\\vtc2027_spring\\evidence\\validation_v1\\layer1_controlled_trials.csv"}
- `LAYER2_MULTIPATH_STRESS_QA`: **BLOCKED**
  - {"error": "missing experiment output: E:\\GNSS_Multipath_Project\\docs\\vtc2027_spring\\evidence\\validation_v1\\layer2_multipath_stress_trials.csv"}
- `LAYER3_NATIVE_MODEL_QA`: **BLOCKED**
  - {"error": "missing experiment output: E:\\GNSS_Multipath_Project\\docs\\vtc2027_spring\\evidence\\validation_v1\\layer3_native_model_support.csv"}
- `DLL_BIAS_QA`: **BLOCKED**
  - {"error": "missing experiment output: E:\\GNSS_Multipath_Project\\docs\\vtc2027_spring\\evidence\\validation_v1\\dll_code_bias_cases.csv"}
- `PAPER_ADMISSION_RECOMMENDATION`: **BLOCKED**
  - {"dll_improved_event_count": null, "layer1_minus10_rate": null, "layer1_minus5_rate": null, "layer2_minus12_rate": null, "layer2_minus8_rate": null, "recommendation": "BLOCKED"}

## Predeclared paper-admission gate

- Layer 1 recovery at -5 dB: `None` (required >= 0.80)
- Layer 1 recovery at -10 dB: `None` (required >= 0.80)
- Layer 2 recovery at -8 dB: `None` (required >= 0.70)
- Layer 2 recovery at -12 dB: `None` (required >= 0.70)
- DLL events with lower error-aware median absolute bias: `None` (required >= 3/4)
- Paper-admission recommendation: **BLOCKED**

## Scientific interpretation boundary

- Layer 1 backgrounds are not labeled LOS or multipath-free.
- Only injected paths have known truth in Layers 1--2; native paths are consistency references.
- Layer 3 is native model-fit support, not physical-reflector ground truth.
- DLL output is a signal-level receiver-model result, not PVT, pseudorange, or positioning improvement.

## Gate

The report stops here. Manuscript integration requires a separate author/Commander admission decision.
