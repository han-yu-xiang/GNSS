# VTC three-layer validation workspace

This directory implements the author-approved validation plan in
`docs/vtc2027_spring/VTC_SEMI_SIM_AND_APPLICATION_VALIDATION_PLAN.md`.

The validation namespace is deliberately separate from production:

```text
docs/vtc2027_spring/evidence/validation_v1/
```

The author-approved Python-only workflow is:

1. run `python scripts/analysis/vtc_validation/freeze_validation_contract.py`;
2. inspect and approve the generated `validation_contract.json`;
3. run `python scripts/analysis/vtc_validation/test_validation_contract.py -v`;
4. run the four Python entrypoints sequentially with one worker and below-normal
   process priority; the scripts must not start, attach to, pause, or terminate
   MATLAB and must not interact with the production runner or its lock;
5. run the layer-specific Python audits/tests;
6. stop at the independent QA and author paper-admission gate.

The scripts must not call the production wrapper, change `scenes/**/sage_results`,
modify evidence CSVs, or use `Resume=true`.

The superseded `.m` validation drafts are retained for provenance only. They are
not execution entrypoints for this approved run.
