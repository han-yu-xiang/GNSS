# Darkroom multi-seed collection

This is an isolated 5-minute collection of generated channel parameter tables.
It is not an RF replay, PVT result, vehicle validation result, or absolute-power calibration.

- table count: 48
- duration per table (ms): 300000
- matrix: 4 environments x 3 modes x 4 realizations
- modes: GOOD and POOR are dry v2.2 quality profiles; RAIN is the matching GOOD realization plus RainPooled.
- Rain #NN is derived only from the corresponding GOOD #NN table.
- every table contains Low/Mid/High path IDs 0..3 at each millisecond.
- only the frozen v2.2 generator and frozen Rain Stage3 effect layer are used.
- raw IQ, MATLAB, SAGE, GNSS-SDR, 20.46 MHz processing, and gold labels are not used.

Use the manifest and SHA files as the immutable provenance anchor.  A failed or partial namespace must not be resumed; use a new collection namespace for any retry.
