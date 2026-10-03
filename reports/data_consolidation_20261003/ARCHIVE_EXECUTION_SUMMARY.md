# Archive execution summary

Execution date: 2026-10-03  
Project: E:\GNSS_Multipath_Project  
Archive root: E:\GNSS_Multipath_Project_ARCHIVE  
Git branch: review/vtc-final-language-layout-cleanup-20260917 (unchanged)

## Outcome

ARCHIVE_ROOT_CREATED=YES  
MOVE_METHOD=Move-Item (all source and destination paths are on E:)  
MAINLINE_SAGE_NAMESPACES_MOVED=78  
MAINLINE_SAGE_BYTES_MOVED=229230888  
MAINLINE_SAGE_FILES_MOVED=1649  
DARKROOM_UNITS_MOVED=17  
DARKROOM_BYTES_MOVED=16924172871  
DARKROOM_FILES_MOVED=1037  
ALL_95_DESTINATIONS_VERIFIED=YES  
DARKROOM_KEEP_ITEMS_MOVED=0  
DARKROOM_REVIEW_ITEMS_MOVED=0  
DARKROOM_KEEP_ITEMS_REMAINING=97  
DARKROOM_KEEP_BYTES_REMAINING=268324598715  
DARKROOM_REVIEW_ITEMS_REMAINING=61  
DARKROOM_REVIEW_BYTES_REMAINING=294821602469

Post-move verification found every approved source namespace/unit absent from its original path, every destination present, and destination file count and total bytes equal to the pre-move record. No destination was overwritten. The 97 KEEP and 61 REVIEW paths remain present.

## 48-table size drift gate

DARKROOM_48_TABLE_INTEGRITY=PASS  
SIZE_DRIFT=BENIGN_METADATA_ADDITION  
FORMAL_TABLES=48  
FORMAL_TABLE_BYTES=14151548683  
RECURSIVE_COLLECTION_FILES=57  
RECURSIVE_COLLECTION_BYTES=14151659699  
NON_TABLE_METADATA_FILES=9  
NON_TABLE_METADATA_BYTES=111016  
TABLE_HASHES_MATCH_GENERATION_AND_QA=48/48

The exact 111,016-byte difference is the nine non-table README, manifest, QA, receipt, provenance/progress, and released-lock files included in recursive directory size. All remain in the formal collection. Full table/hash detail is in DARKROOM_48_TABLE_SIZE_DRIFT_AUDIT.md.

## Mainline note

The 78 namespaces comprise 77 nav_sage_v2 PRN namespaces plus the legacy G06_nav_sage_v1 namespace. The legacy row was REVIEW in the prior CSV because its row omitted tracking channel and run_context. Before moving, the current log-derived PRN/channel matrix uniquely mapped it to G06/ch4; raw IQ path exists, sample rate is 10.23 MHz, and tracking/telemetry inputs pass. The execution CSV records this correction and the prior status. The previous audit manifest did not contain a paper_related_possible column; the execution record marks that field UNVERIFIED_NOT_CAPTURED_IN_PRIOR_MANIFEST rather than inventing values. Per-row paper review was not used as a move gate, consistent with the explicit user instruction.

## Protected inputs and execution record

- All 19 Mainline raw-IQ paths remain present; this was path/metadata verification only, with no raw-IQ content read.
- All 130 PRN/channel tracking and telemetry file pairs remain present.
- Final Darkroom 48-table collection, its manifests/QA/provenance, final 0919 GNSS-SDR result, 0919 input freeze, final models/config/code, and reports were not moved.
- All 61 REVIEW items remain at their source paths; this includes the 0913 raw IQ and 0919 .rfcatcher companions.
- No MATLAB, SAGE, GNSS-SDR, or batch was run.
- No files were physically deleted; the approved units were moved to the external archive root.
- No Git branch switch, commit, or push occurred. Existing user worktree changes were left intact.

## Execution artifacts

- archive_move_preflight.csv: persistent pre-move source/destination/count/size/mtime record for all 95 approved units.
- mainline_sage_archive_execution.csv: per-namespace Mainline move/verification results.
- darkroom_archive_execution.csv: per-unit Darkroom move/verification results.

