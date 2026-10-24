# Stage2 SAGE-only V0 final review package

Start with `v0_model_report.md`, then `model_summary.json` and the CSV tables.
These are real-data results, not synthetic experiments. Unit tests alone use
synthetic fixtures. The full runtime products remain on C: in the isolated
checkout's `dataset_generation_logs/channel_modeling/mainline_1023_stage2_v0_20261024T132210Z/`.

This light review package excludes the full path/window tables, PDFs and
production snapshot; it includes six PNG figures and coordinate-free summaries.
`runtime_artifact_manifest.json` binds the full private runtime directory,
not a claim that every private artifact is included here. Copied artifacts
retain their runtime bytes. Review/recount evidence is added separately.

The execution HEAD was parent614d49f; new statistical sources were uncommitted.
The effective executed code version is the three `code_files` SHA256 values
in model_summary, also in numerical_recount. Delivery verifies identical Git
blobs, so the parent HEAD is not mistaken for the implementation version.

`numerical_recount.json` records exact keys/counts,39 independently computed
closed-form held-out scores,34 output and20 input hash checks,33/33 targeted
tests, and unchanged numerical CSVs across the two review fixes. Read
`independent_review.md` for what the separate reviewer did and did not verify.

Status is EXPLORATORY_V0_COMPLETE_WITH_LIMITATIONS. Gate E/F, full CIR/physical
channel-model validation and Phase-2 AI remain pending. Task5 continues under
its existing release; V0 did not control it.
