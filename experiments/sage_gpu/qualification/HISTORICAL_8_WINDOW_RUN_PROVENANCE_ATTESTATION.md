# Historical 8-window run-level provenance attestation

This attestation is limited to the eight named historical GPU Stage2 qualification results below. It does not alter their JSON artifacts and does not claim that those files directly recorded the Frozen SAGE SHA.

```ini
attestation_scope=historical_first_8_gpu_stage2_qualification_windows
source_review_commit=c7a542daacf66dae4a098d95bad2693505e622c1
expected_frozen_sage_sha256=bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c
evidence_driver_path=experiments/sage_gpu/qualification/Invoke-GpuStage2Qualification.ps1
evidence_driver_blob_sha1=f6ed124ddb8d9525a54dcd5f702e242dce64eff6
evidence_snapshot_path=reports/project_stage_review_20261005/GNSS_PROJECT_STAGE_SNAPSHOT.md
evidence_snapshot_blob_sha1=a344c0e1b2c9a303f2f7355b3b27e35d8f1b1b2a
qualification_windows=8
PER_WINDOW_EMBEDDED_FROZEN_SHA=MISSING
FROZEN_SHA_PROVENANCE_SOURCE=RUN_LEVEL_PREEXECUTION_GUARD_PLUS_CONTEMPORANEOUS_COMMITTED_SNAPSHOT
THIS_ATTESTATION_DOES_NOT_MODIFY_HISTORICAL_RESULT_JSON=YES
```

## Evidence basis

The immutable review commit contains the qualification driver with an entry preflight that hashes `scripts/sage_pipeline/run_nav_sage_pipeline.m`, compares it exactly to the expected SHA above, and throws `SAGE_SOURCE_HASH_MISMATCH` before qualification proceeds on mismatch. The same commit's stage snapshot records eight executed windows, eight CPU-to-formal-reference passes, eight GPU structural passes, and that qualification stopped at the `Q_G06_W6850` identity gate before that window's raw-IQ access.

This is a run-level attestation: the committed pre-execution guard plus the contemporaneous committed snapshot tie the eight completed results to that qualification run. The per-window JSON files do not contain `frozen_sage_sha256`; no SHA was added to them after the fact.

For each result, the local worktree blob was compared with `git rev-parse c7a542daacf66dae4a098d95bad2693505e622c1:<result-path>`. All eight local blobs matched the commit blobs byte-for-byte. The JSON status fields were also checked as `COMPLETE`, `cpu_production_reference=PASS`, and `gpu_structural_equivalence=PASS`.

| Qualification ID | Result path | Git blob SHA-1 | Byte-identical | Historical status |
|---|---|---|---|---|
| Q_G28_W38 | `experiments/sage_gpu/qualification/results/Q_G28_W38.json` | `e11cebce04677c553eac8e53af2c43ad2c1d152e` | YES | COMPLETE; CPU PASS; GPU PASS |
| Q_G28_W298 | `experiments/sage_gpu/qualification/results/Q_G28_W298.json` | `68baed91877e2601c3b1e080078463424c0ec121` | YES | COMPLETE; CPU PASS; GPU PASS |
| Q_G28_W725 | `experiments/sage_gpu/qualification/results/Q_G28_W725.json` | `9ec1c3aded6cc563d0a69cd3d9d6a16751412d4a` | YES | COMPLETE; CPU PASS; GPU PASS |
| Q_G28_W226 | `experiments/sage_gpu/qualification/results/Q_G28_W226.json` | `ee5932e293a01d68cd6e69a0465851de46223e1f` | YES | COMPLETE; CPU PASS; GPU PASS |
| Q_G03_W1 | `experiments/sage_gpu/qualification/results/Q_G03_W1.json` | `22268233ef2e453fb0192a2beb84426baafaf1a4` | YES | COMPLETE; CPU PASS; GPU PASS |
| Q_G03_W9 | `experiments/sage_gpu/qualification/results/Q_G03_W9.json` | `ec79bd590e81883007ae385a20993ec0ab4b88e0` | YES | COMPLETE; CPU PASS; GPU PASS |
| Q_G03_W11 | `experiments/sage_gpu/qualification/results/Q_G03_W11.json` | `77e5116d57f1008e48a495ce891e261da8db2c43` | YES | COMPLETE; CPU PASS; GPU PASS |
| Q_G03_W173 | `experiments/sage_gpu/qualification/results/Q_G03_W173.json` | `4a9e3c45f557e7a5a8dbe9f38070c8adebf80a1c` | YES | COMPLETE; CPU PASS; GPU PASS |

## Limits and use

The machine-readable companion is `HISTORICAL_8_WINDOW_RUN_PROVENANCE_ATTESTATION.json`. Resume fallback is permitted only for these eight IDs, only while the attestation names the exact source commit and Frozen SHA, and only after runtime Git checks confirm both the attested commit blob and local result blob match. A modified result, an unknown ID, an incomplete/mismatched attestation, or any future result without its own embedded Frozen SHA fails closed.

No historical result JSON, formal Stage output, Frozen SAGE source, or qualification sample was modified to create this attestation.
