---
name: gnss-sage-project-commander
description: "Govern GNSS/SAGE pipeline, production, QA, provenance, VTC evidence, and paper-support work in E:\\GNSS_Multipath_Project. Use for any task that reads or changes GNSS/SAGE artifacts, creates or validates production requests, runs or audits Stage0-Stage4, updates VTC evidence, or synchronizes engineering/paper handoffs."
---

# GNSS SAGE Project Commander

## Scope

Use this skill for project-specific execution discipline, scientific semantics, and production governance. Treat it as a narrow project commander, not as a GNSS tutorial, generic MATLAB guide, generic writing skill, or substitute for the user's/Commander's decisions.

Keep the project root fixed at E:\GNSS_Multipath_Project. Do not expand scope, invent files, or redesign a stable pipeline merely because a task could be made more elaborate.

## Authoritative state sources

Read the relevant current sources before acting:

- Engineering state: docs/GNSS_SAGE_ENGINEERING_HANDOFF_CURRENT.md (唯一 engineering status source).
- Paper/scientific state: docs/GNSS_SAGE_PAPER_HANDOFF_CURRENT.md (唯一 paper status source).
- Paper asset navigation: docs/PAPER_WORKSPACE_INDEX.md (asset structure only, not experiment status).
- VTC workspace: docs/vtc2027_spring/, especially VTC_PLAN.md, EVIDENCE_MATRIX.md, VTC_PRODUCTION_PRIORITY_QUEUE.md, MANUSCRIPT_OUTLINE.md, and FIGURE_TABLE_PLAN.md.
- Accepted 10.23 MHz production count: dataset_generation_logs/production_monitoring_10MHz/production_summary_10MHz.csv and its report. Do not hand-count from chat history or overwrite the summary with an inferred count.

Do not create parallel Engineering/Paper handoffs, a second production status system, or a new status/plan file merely to record temporary state. Do not treat a README, QA report, planning document, or daily handoff as the unique current state source.

After a real change, update only the affected source: update Engineering Handoff for code, execution, QA, hash, environment, or production-state changes; update Paper Handoff for research direction, paper facts, or chapter state; update PAPER_WORKSPACE_INDEX.md only when the paper asset structure changes.

## Start-of-task protocol

1. Read the applicable handoff and the relevant queue, manifest, receipt, QA report, or artifact.
2. Classify the request explicitly as validation, production, QA, VTC evidence, paper support, or planning.
3. Inspect the actual directory, metadata, inventory, manifest, and hashes before using a path or status.
4. State whether raw IQ content, MATLAB, SAGE, batch execution, or file writes are authorized.
5. Preserve Completed, Validated, Implemented, Planned, Not started, and Failed/Frozen distinctions. Never turn a plan or implementation into a result.

If a requested fact is missing, report it as missing. Do not infer channel, geometry, environment, event count, runtime, or scientific meaning from a filename or an old handoff.

## Production contract

Treat every production request as immutable and single-task by default. Require:

    execution_mode = new_only
    new_only = true
    resume_allowed = false
    max_parallel_matlab = 1

Use this execution chain:

    immutable request
      -> normal-user wrapper validation
      -> executor revalidation
      -> MATLAB invocation
      -> Stage0-Stage4
      -> independent QA
      -> production summary and necessary handoff sync

For new-only production, the MATLAB expression must explicitly contain 'Resume', false; never rely on MATLAB defaults. The expected output namespace must be absent before execution. Reject overwrite, resume, deletion of old scientific artifacts, modification of old immutable requests, automatic channel changes, and automatic selection of multi-channel-blocked tasks. Preserve interrupted/failed artifacts; do not silently resume or clean them up.

The approved execution boundary is a normal non-administrator TJ-CHANNEL\Jing_ PowerShell 7 session using Invoke-BatchSageWindows.ps1. Do not start MATLAB from the Codex sandbox. Require MATLAB startup marker and exit code 0 before the executor is called. Execute one approved task at a time unless the user explicitly authorizes parallelism, and never auto-generate or auto-start the next request.

Keep production on the supported 10.23 MHz path. Do not run 20.46 MHz until a separately designed and validated pipeline is explicitly approved.

## Stage0-Stage4 scientific semantics

Keep the following meanings fixed:

- Stage0: align valid NAV symbols and construct complete 40 ms observation windows. It is not multipath detection.
- Stage1: correlation-based candidate screening. A candidate is not a confirmed multipath event.
- Stage2: fractional delay/Doppler SAGE model evaluation for L=1,2,3,4. L>=2 is not confirmed multipath.
- Stage3: temporal persistence and reliable-center validation using delay/Doppler/power/neighbor evidence. A Stage3 reliable center is not confirmed multipath.
- Stage4: 100 ms multi-snapshot joint estimation and final path confirmation.

Use the fixed confirmed criterion only:

    joint_valid == 1
    AND joint_multipath_count > 0
    AND the corresponding stage4_joint_paths row has is_multipath == 1

Do not label an intermediate candidate, model order, reliable center, or coarse/sampled promotion as a confirmed event/path.

For a valid zero-event output, write: “under the current Stage4 confirmation criterion, this task produced zero confirmed multipath events.” In Chinese: “在当前 Stage4 联合确认准则下，该任务未产生 confirmed multipath event。” Never write that a satellite or environment has no physical multipath, is LOS, or is reflection-free; high elevation and Highway/Open labels do not imply zero events.

## Validation, artifacts, and accepted production

Distinguish these categories in every report:

1. reference multi-PRN validation;
2. Wave-A or other cross-task validation;
3. long-run/scalability validation;
4. complete scientific artifact with QA;
5. accepted production task.

Do not automatically count validation or a scientific artifact as accepted production. Count only QA-passed tasks represented by the current production summary and accepted-state rules.

Protect historical A3 F1023_V70_D0120_P5/G16/ch1: its Stage0-Stage4 artifact and scientific QA are usable for bounded pipeline/scientific validation, but its old request recorded resume_allowed=false while the actual invocation used Resume=true. It is not accepted production, must not be rerun, resumed, overwritten, or counted by inference.

Keep raw-coarse/sampling/v3 experiments separate from full-SAGE production. The v3 acceleration experiment is an immutable negative/frozen result after posterior coverage failure; do not tune it against gold, use it as a production selector, or let it block the accuracy-first full-SAGE dataset route.

## Long-term research and VTC route

Preserve the long-term chain:

    raw GNSS IQ
      -> GNSS-SDR tracking/navigation
      -> NAV-aided full SAGE Stage0-Stage4
      -> confirmed event/path
      -> unified event/path database
      -> path-level channel parameters
      -> environment/elevation-conditioned statistical GNSS channel model

Candidate future parameters include PDP, RMS delay spread, Doppler spread, Ricean K-factor, path count, mean excess delay, relative-power statistics, and path lifetime/temporal stability. Do not claim the event database, channel-parameter database, statistical model, or all scenes are complete unless current artifacts prove it.

Treat VTC2027-Spring as a temporary high-priority evidence branch, not a replacement for the long-term route. Prefer work that closes an explicit VTC evidence gap, but never change scientific criteria or the production manifest to make a paper result look better.

Use the VTC strategy:

    small wave -> independent QA -> evidence-matrix update -> Commander decision -> next task

Prepare or execute one immutable VTC production task at a time. Environment labels (Special Reflective, Highway/Open, Mountain/Valley) and LOW/MID/HIGH planning context are coverage metadata, not event predictions. Each can legitimately yield confirmed, zero-event, or Stage4-rejected results.

## QA behavior

For read-only QA, inspect the request/manifest, execution and environment receipts, status history, stdout/stderr, task log, output directory, run context, and required Stage files. Check at least:

- request scope, SHA, manifest/task/source hashes, and normal-user execution contract;
- new_only and absence of checkpoint reuse or old namespace overwrite;
- output completeness and non-empty required files;
- Stage0 subset/identity, Stage1 scan/candidate counts, Stage2 model-order accounting, Stage3 center linkage, and Stage4 linkage;
- finite confirmed path fields and the strict Stage4 criterion;
- output isolation, locks, runtime/progress, warnings, partial/failed markers, and provenance.

Do not modify existing SAGE artifacts, manifests, requests, metadata, inventory, or QA evidence during QA. Do not automatically rerun a failed task, adjust thresholds to improve a result, or treat zero-event as failure. A summary-monitoring refresh may write only its designated monitoring outputs and must be reported as an audit action, not an experiment.

## Commander boundary and minimal change

Require explicit user/Commander direction before releasing a new production wave, broadening VTC scope, changing the confirmation criterion, starting 20.46 MHz, starting full statistical modeling, deleting artifacts, or adding a research branch. Do not decide that “the paper needs more experiments” and expand the scope yourself.

Apply minimal necessary change:

- perform read-only work without writes when possible;
- edit an existing authoritative file instead of creating a parallel status file;
- avoid opportunistic refactors and new dependencies;
- change stable pipeline code only for a documented, reproducible bug;
- preserve old namespaces and hashes; use a new versioned namespace for a genuinely new experiment.

## Completion report

End each substantial task with:

- what changed and the exact artifact paths/hashes;
- validation or experiment result, with intermediate versus Stage4-confirmed semantics separated;
- current status using the controlled vocabulary;
- Handoff impact: with Engineering and Paper update required yes/no;
- NEXT_DECISION_REQUIRED= and the decision owner when a Commander choice is needed;
- explicit execution record: raw IQ read, MATLAB, SAGE, batch, and data/artifact modifications.

Wait for the Commander after a gated task. Do not automatically continue to T1-2/T1-3, another production task, another wave, or a new analysis branch.
