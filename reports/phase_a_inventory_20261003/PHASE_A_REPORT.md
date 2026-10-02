# Phase A — metadata-only project inventory

Generated: 2026-10-03. This is a project-external, non-authoritative inventory snapshot; it does not replace or update any canonical handoff.

PHASE=PHASE_A  
STATUS=COMPLETE_WITH_BLOCKERS

## FACTS

- Branch: review/vtc-final-language-layout-cleanup-20260917; HEAD: 0e0b3c7452e08e448c40e7fc333022a3ad67cc2f. GitHub remote branch points to 46c9359895895296876729644179173b49ff3637. Local is 3 commit(s) ahead and 0 behind that remote snapshot. The local-only commits and worktree changes are not uploaded.
- Worktree: 5 tracked changed entries, 84 untracked entries, 0 staged entries. Existing work is presumed user-owned and was left untouched.
- Mainline initial inventory: 19 logical records (13 at 10.23 MHz; 6 at 20.46 MHz), total raw size 92336825856 bytes. Metadata and per-scene GNSS-SDR config are present for all 19. The dataset inventory snapshot says GNSS-SDR SUCCESS; physical SAGE files are present in 13 scenes, but this does not establish QA or accepted production. The six 20.46 MHz records are not validated for current SAGE.
- Darkroom: the engineering handoff records 48/48 0919 GNSS-SDR artifact QA PASS, 31 tasks with position output observed, 17 without position output, and 0/48 SAGE-ready. The 0913 audit records 6/8 QA PASS and 2/8 inconclusive. Engineering handoff section 90 says all nine Rain r4 outputs have independent QA PASS; the Darkroom handoff’s top-level NOT_STARTED state is stale/conflicting.
- Preliminary enumerated CORE copy candidate: 577023838962 bytes (577.024 GB; 537.4 GiB). Optional historical Rain diagnostics add 4956094 bytes. This is not an exact Phase C copy manifest and excludes unresolved model/mainline parent dependencies.
- E: free space: 437765275648 bytes (407.7 GiB). Required reserve under the plan is 200037996954 bytes; usable after reserve is 237727278694 bytes. The current CORE candidate exceeds raw free space by 139258563314 bytes and the safety-adjusted budget by 339296560268 bytes.
- The pasted plan attests that the VTC paper was submitted. The scoped repository records still say author review/no submission; no exact submitted PDF, portal receipt, submission commit, or figure-to-source binding was found. Submission state therefore remains UNVERIFIED.
- The current formal main.tex points to three PDFs dated 2026-08-31 that are not bound by the 2026-08-22 figure manifest. They remain candidates, not a freeze selection.
- README calls the v3 darkroom briefing deck current, while local v4/v5 files also exist; v4/v5 status is UNKNOWN.

## CREATED

- project_asset_inventory.csv: 335 scoped entries, including dirty-worktree paths.
- paper_candidate_inventory.csv: 27 candidate/source/evidence rows; not a freeze manifest.
- darkroom_asset_inventory.csv: 157 scoped metadata rows, including 107 raw/companion/dependency files and selected result-root summaries.
- mainline_raw_inventory.csv: 19 logical raw rows.
- PHASE_A_REPORT.md.

## COPIED

- NONE.

## NOT_MODIFIED

- Project source and scientific artifacts were not modified, moved, deleted, or overwritten.
- Raw IQ contents were not opened, decoded, sampled, or newly hashed. Any SHA-256 values in the inventory are pre-existing manifest/metadata values only.
- MATLAB, SAGE, GNSS-SDR, batch, and production were not run.
- No branch switch, cleanup, reset, commit, or push.

## BLOCKERS

- Paper freeze: exact submitted artifact and provenance are unverified; user-attested submission conflicts with repository records.
- Darkroom archive: current enumerated candidates do not fit on E: with the required reserve. Do not start partial copying. Further parent dependencies may increase the required size.
- Mainline SAGE status: inventory snapshot and physical output presence disagree; QA/accepted-production status was not adjudicated in Phase A.
- Darkroom presentation version: v3 is cited as current; v4/v5 remain unverified.

## NEXT

Phase A stops here. Wait for user direction. Before Phase B, resolve or explicitly accept the paper candidate as unverified. Before Phase C/D, choose a larger destination or approve a narrower scope, then prepare an exact no-overwrite copy manifest.

Tracked modified paths observed:
- docs/GNSS_SAGE_ENGINEERING_HANDOFF_CURRENT.md
- docs/darkroom_completion_report_materials/01_GB_T_45086_1_2024_PROJECT_RELATION_CN.md
- docs/darkroom_completion_report_materials/04_EXISTING_DARKROOM_ASSET_INDEX_CN.md
- docs/darkroom_completion_report_materials/README.md
- docs/vtc2027_spring/supplemental_data_outputs/channel_model_scientific_risk_text_revision_review_20260913_layout_cleanup_20260915/manuscript/latex/main.tex

Output folder: E:\GNSS_Multipath_Project_CONSOLIDATED_20261002