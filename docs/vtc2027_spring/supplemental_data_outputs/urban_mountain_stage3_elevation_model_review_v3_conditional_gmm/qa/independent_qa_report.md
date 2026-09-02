# Independent QA — Conditional Partially Pooled 3-D GMM

Status: `PASS_WITH_LIMITATIONS`

## Recomputed support

- Primary rows: `518`
- Elevation-conditioned rows: `487`
- Missing-elevation rows retained for environment parent only: `31`
- Tracks/scenes/cells: `236` / `9` / `6`

## Model and validation

- Selected model: `K=3`, `κ=16.0`.
- Candidate/LOSO/model-bootstrap/paired-bootstrap rows: `12` / `108` / `12000` / `2000`.
- Review draws: `24576` (`4096` per cell).
- All mixture weights, finite values, component ordering, and shared covariance positive-definiteness checks passed.

## Cell support

- `DATA_SUPPORTED`: Urban-MID, Urban-HIGH, Mountain/Valley-MID.
- `STRONGLY_PARTIALLY_POOLED`: Urban-LOW, Mountain/Valley-LOW, Mountain/Valley-HIGH.

## Limitations

- The six cells are conditional descriptive model outputs, not a complete stochastic channel model.
- No component is assigned a reflector class or physical propagation identity.
- The existing v2 marginal-plus-copula baseline was not directly compared in Task 5.

Execution boundary: no raw IQ, MATLAB, SAGE, Stage4 source, formal manuscript, canonical figures/tables, Evidence Matrix, or handoff was modified.
