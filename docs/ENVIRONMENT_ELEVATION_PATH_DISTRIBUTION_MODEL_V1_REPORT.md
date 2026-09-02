# Environment × Elevation Path-Distribution Model v1

## 1. Execution scope and status

This report records the first Python-only build and independent QA of the frozen environment-conditioned, elevation-conditioned confirmed-NLOS path distribution layer. The build used only the existing Stage4-confirmed path-parameter partition. It did not read raw IQ, tracking files, MATLAB/SAGE inputs, or any 20.46 MHz data, and it did not modify any SAGE result, source partition, metadata, inventory, production manifest, or the separate receiver lock-loss model.

The bounded model status is:

```text
PATH_DISTRIBUTION_MODEL = COMPLETED_WITH_SPARSE_PRIOR_CELLS
MODEL_QA = PASS_WITH_LIMITATIONS
READY_FOR_DARKROOM_GENERATOR_INTEGRATION = NO
DARKROOM_GENERATOR = NOT_STARTED
```

`COMPLETED_WITH_SPARSE_PRIOR_CELLS` means that the versioned conditional NLOS path-distribution layer was built and independently checked. It does not mean that the complete four-path, millisecond darkroom generator or a universal physical channel model has been completed.

## 2. Frozen input and provenance

| Item | Value |
|---|---|
| Configuration | `configs/channel_modeling/environment_elevation_path_distribution_v1.json` |
| Configuration SHA-256 | `94ffdd882e70c2217e51a06deff7466bcccfc25f78d505f2d8dd9d4807bf2cb7` |
| Source | `dataset/multipath_event_database/v1/partitions/parameter_set_id=parameters_20260825_stage4_path_v1/facts/path_parameters.csv` |
| Source SHA-256 | `2a44913d1c06f78d2748428b1d72f1b4712a6b5d3f33fc598a14fe17a3e3414a` |
| Source population | 100 environment-ready confirmed multipath paths |
| Elevation-ready population | 84 paths |
| Elevation-excluded population | 16 paths; retained for environment/global parents only |
| Represented scenes | 11 |
| Protected pipeline SHA-256 | `bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c` |
| Output namespace | `dataset_generation_logs/channel_modeling/environment_elevation_path_distribution_v1_20260826_r1/` |
| Model manifest SHA-256 | `4f24dd3a5532526ef9966288ea7de9d863fabd812abe07a811647095e5368f3c` |

The selection and fitting flags in the manifest are `gold_labels_used_for_selection=false` and `posterior_gold_used_for_selection=false`. The input is the already QA-passed Stage4 path-parameter partition; no new posterior replay was performed.

## 3. Cell coverage and support

Elevation bins are frozen as LOW `[0,30)`, MID `[30,60)`, and HIGH `[60,90]` degrees. Counts below are direct elevation-ready confirmed multipath paths, not estimates of multipath occurrence.

| Environment | LOW | MID | HIGH |
|---|---:|---:|---:|
| Urban | 0 (`PRIOR_ONLY`) | 30 (`DATA_SUPPORTED_WITH_GROUPED_VALIDATION`) | 10 (`DATA_SUPPORTED_WITH_GROUPED_VALIDATION`) |
| Special Reflective | 19 (`DATA_SUPPORTED_WITH_GROUPED_VALIDATION`) | 1 (`PRIOR_DOMINANT`) | 2 (`PRIOR_DOMINANT`) |
| Mountain/Valley | 5 (`SPARSE_PARTIAL_POOLING`) | 9 (`SPARSE_PARTIAL_POOLING`) | 4 (`SPARSE_PARTIAL_POOLING`) |
| Highway/Open | 0 (`PRIOR_ONLY`) | 3 (`SPARSE_PARTIAL_POOLING`) | 1 (`PRIOR_DOMINANT`) |

The two exact empty cells are Urban–LOW and Highway/Open–LOW. They inherit their environment parent distribution exactly and remain visibly `PRIOR_ONLY`; they are not empirical observations. The 16 paths without reliable event-level elevation were not assigned to a band and did not enter any cell likelihood.

## 4. Marginal family selection

One global family was selected for each fitted physical parameter using leave-one-scene-out held-out log likelihood across all 11 represented scenes. The candidate order and tie tolerance were frozen before fitting.

| Parameter | Candidates | Selected family |
|---|---|---|
| `relative_delay_ns` | lognormal, gamma, Weibull | `lognormal` |
| `relative_doppler_hz` | Student-t, normal, Laplace | `laplace` |
| `relative_power_db` | Student-t, normal, Laplace | `normal` |

Fitting remains in the native model units: positive excess delay in ns, signed relative Doppler in Hz, and relative power in dB. Linear amplitude is derived only through the fixed `10^(relative_power_db/20)` transform; positive dB values were retained.

## 5. Hierarchy and dependence

The fitted hierarchy is global parent → environment parent → environment×elevation cell. Each environment parent uses all paths in that environment, including elevation-ineligible paths, plus 64 deterministic global-parent quantiles with total prior-equivalent weight 8. Each non-empty cell uses its direct elevation-ready paths plus 64 environment-parent quantiles with the same total prior-equivalent weight. Empty cells use the exact environment parent and are recorded as `environment_parent_only`.

Joint dependence is represented by an environment-level Gaussian copula over delay, signed Doppler and power dB. It is shrunk toward the global copula with the frozen weight `n_environment/(n_environment+10)` and projected to a correlation matrix with eigenvalue floor `1e-6`. No unsupported cell-specific covariance was estimated.

## 6. Uncertainty and diagnostic QA

- Scene-block bootstrap: 1,000 replicates, seed `20260826`; complete scenes, rather than adjacent individual paths, were resampled.
- Predictive QA draws: 4,096 per cell with the frozen base seed `20260827` and deterministic cell seed offsets.
- Independent checks passed source hash and Stage4 label semantics, 100/84/16 accounting, all 12 cells, 36 cell marginal records, prior-only inheritance, family-selection grouping, copula symmetry/PSD/shrinkage, marginal normalization, finite positive delay/amplitude draws, and output hashes.
- Grouped-validation status is `PASS_WITH_LIMITATIONS` because sparse cells do not support the same cross-scene evidence as the larger cells.

Independent QA artifact:

`dataset_generation_logs/channel_modeling/environment_elevation_path_distribution_v1_20260826_r1/independent_qa_report.md`

with result JSON `independent_qa_result.json`.

## 7. Output artifacts

The new-only output namespace contains the source audit, 12-cell coverage, candidate-family scores, global/environment marginals, 36 cell distributions, environment copula parameters, cell index, bootstrap intervals, predictive diagnostics, the sampling contract, model manifest, build receipt, and model report. The build receipt records status `COMPLETED` and the model manifest hash above.

The sampling contract is deliberately not a final simulator table. It specifies the output units and provenance needed by a later generator: relative delay in ns, signed relative Doppler in Hz, and linear relative amplitude; the default main-path reference, phase evolution, lock-loss, absolute-power, path-count and fixed four-row composition remain external/deferred decisions.

## 8. Scientific and engineering boundary

This result is a conditional distribution of confirmed NLOS path parameters given environment and, where available, event-level elevation. It cannot by itself estimate the probability that a random observation contains multipath because the source table contains confirmed multipath paths only. The separate receiver lock-loss diagnostic model is not silently merged into this path model.

Still deferred are the main/common-path gain and absolute power mapping, the relationship between lock-loss diagnostics and signal amplitude, phase initialization and Doppler-continuous phase evolution, occurrence/path-count and inactive-slot behavior, path lifetime, and the fixed four-path millisecond output contract. Highway/Open and several low-support cells require explicit prior/partial-pooling labeling in any downstream use. The final darkroom generator therefore remains `NOT_STARTED`.

