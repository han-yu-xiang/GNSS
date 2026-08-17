# VTC2027-Spring Submission Requirements & Final Gate Audit

**Audit date:** 2026-08-16 (Asia/Shanghai)  
**Submission target:** IEEE VTC2027-Spring, Hamburg, Regular Paper  
**Scope:** Initial-submission and final/revision requirements only; no submission was attempted.

## 1. Official sources and evidence boundary

This audit uses the current VTC2027-Spring Call for Papers, the linked public TrackChair conference page, and official IEEE Author Center guidance. The public TrackChair page was inspected without logging in. Fields that appear only after authentication, and rules not stated on the current VTC2027-Spring pages, remain `NOT_CONFIRMED` rather than being inferred from earlier VTC editions or unrelated conferences.

| Source | URL | Use |
|---|---|---|
| VTC2027-Spring home / dates | https://events.vtsociety.org/vtc2027-spring/ | Current conference calendar |
| VTC2027-Spring Call for Papers | https://events.vtsociety.org/vtc2027-spring/call-for-papers-2/ | Regular-paper length, deadline, overlength policy, topics |
| VTC2027-Spring public TrackChair page | https://vtc2027spring.trackchair.com/ | Public track descriptions and submission entry point |
| IEEE Author Center: templates | https://conferences.ieeeauthorcenter.ieee.org/write-your-paper/authoring-tools-and-templates/ | Generic IEEE conference template guidance |
| IEEE Author Center: structure | https://conferences.ieeeauthorcenter.ieee.org/write-your-paper/structure-your-paper/ | Abstract and keyword guidance |
| IEEE Author Center: finalize | https://conferences.ieeeauthorcenter.ieee.org/get-published/finalize-your-paper/ | Final-paper metadata and PDF eXpress qualification |
| IEEE Author Center: Xplore requirements | https://conferences.ieeeauthorcenter.ieee.org/write-your-paper/meet-ieee-xplore-requirements/ | Conditional PDF compliance checks |

## 2. Requirement matrix

| Requirement | Initial submission | Final/revision | Official source | Status | Action required |
|---|---|---|---|---|---|
| Regular-paper deadline | 1 September 2026 | Calendar lists paper revisions due 15 March 2027; exact camera-ready upload deadline is not separately exposed | VTC home / CFP | **Confirmed for calendar** | Submit before the initial deadline; confirm post-acceptance instructions later |
| Paper type | 5-page original, unpublished full paper | Final version remains subject to conference publication instructions | CFP | **Confirmed** | Preserve originality/unpublished status |
| Page limit | 5 pages without overlength charge; up to 7 pages is permitted with charges; review submissions should not exceed 8 pages | Up to 7 pages with the stated additional-page charges | CFP | **Confirmed** | Keep the internal target at no more than 5 pages |
| Overlength | Additional pages are charged at USD 100 per page, up to two pages | Charge is stated for registration and final-paper submission | CFP | **Confirmed** | No overlength planned |
| Template | CFP links official IEEE final-paper guidance but does not expose a VTC-specific class on the current public pages | Same; final-paper instructions are not fully reproduced on the VTC page | CFP; IEEE Author Center | **Partial** | Preserve the IEEE conference template; manually verify the final VTC/IEEE package when available |
| Author visibility / anonymity | Current VTC CFP and public TrackChair page do not state anonymous, single-blind, or double-blind initial review | Not confirmed | VTC CFP; public TrackChair page | **NOT_CONFIRMED** | Commander must confirm in the authenticated portal or with conference instructions before changing the author block |
| Author names | Required if the initial workflow is author-visible; no VTC-specific rule is publicly confirmed | IEEE final guidance requires accurate author names | VTC CFP; IEEE Author Center | **NOT_CONFIRMED for initial** | Do not guess; obtain the real ordered author list after visibility is confirmed |
| Affiliation | Portal requirement not visible without authentication | Final author metadata must be accurate | Public TrackChair; IEEE Author Center | **NOT_CONFIRMED for initial** | Obtain institution, department and city/country for each author if required |
| Email / corresponding author | Portal fields not visible without authentication | Exact final metadata fields not confirmed | Public TrackChair; IEEE Author Center | **NOT_CONFIRMED** | Confirm portal fields and provide real contact data; do not invent values |
| Track | Public page exposes the relevant tracks and says to choose the best fit; chairs may move a paper | Same track assignment process is not otherwise specified | Public TrackChair | **Recommendation ready; not submitted** | Use the primary/secondary recommendation below |
| Keywords | IEEE Author Center recommends 3--5 keywords or phrases | Same guidance | IEEE Author Center: structure | **Locally prepared** | Use the five-keyword candidate below; confirm any portal count limit |
| PDF format | PDF upload is implied by the paper workflow, but a VTC-specific initial file rule is not stated on the public CFP | IEEE Xplore compliance guidance is conditional on conference use of PDF eXpress/PDF Checker | IEEE Author Center: Xplore requirements | **Partial** | Confirm the portal's accepted file type and any conversion rule |
| Font embedding | No VTC-specific initial rule found | IEEE Xplore guidance checks that fonts are embedded or subset | IEEE Author Center: Xplore requirements | **Local pass / conference procedure unconfirmed** | Run PDF eXpress or PDF Checker only if VTC instructs authors to do so |
| PDF compliance / PDF eXpress | VTC2027-Spring does not currently state that PDF eXpress is required for initial review | IEEE says PDF eXpress is used if the conference uses it | IEEE Author Center: finalize and Xplore requirements | **NOT_CONFIRMED** | Wait for the authenticated portal/final-paper instruction; do not claim compliance yet |
| File-size limit | No current VTC limit found on the public CFP or TrackChair page | Not confirmed | VTC CFP; public TrackChair page | **NOT_CONFIRMED** | Check the authenticated upload form before submission |
| Paper size | Current local candidate is US Letter; the VTC CFP does not explicitly state paper size | Not confirmed from VTC-specific instructions | Local PDF QA; VTC CFP | **Local pass / VTC rule unconfirmed** | Confirm the accepted size in the final template/instructions |
| Orientation / encryption | Local candidate is portrait and unencrypted | IEEE Xplore checks include no password/security settings | Local PDF QA; IEEE Author Center | **Local pass** | Recheck the final author-complete PDF |
| Submission portal | Official CFP links the public TrackChair submission page; no account or submission was used | Same portal likely carries later instructions, but no authenticated fields were inspected | CFP; public TrackChair | **Portal reachable / fields unconfirmed** | Commander must complete the portal metadata manually |

## 3. Author-information gate

`AUTHOR_VISIBILITY_RULE = NOT_CONFIRMED`.

The current official public materials do not establish whether the initial review is anonymous or author-visible. The manuscript therefore retains the literal placeholder in `main.tex`:

```latex
AUTHOR INFORMATION TO BE CONFIRMED
```

No real author, affiliation, email, corresponding-author, ORCID or membership information was supplied or inserted. If the portal confirms author-visible review, the following must be supplied for every author: full English name and order, affiliation/department/institution, city/country or region, and email; any corresponding-author, ORCID or membership field must be taken from the actual portal rather than assumed. If the portal confirms anonymous review, the placeholder and any identifying metadata must be removed in a separate controlled manuscript-format change.

`AUTHOR_INFORMATION_REQUIRED = YES`  
`AUTHOR_METADATA_INTEGRATED = NO`

## 4. Track and keyword preparation

### Track recommendation

- `PRIMARY_TRACK = Positioning Technologies, Localization and Navigation` — the paper is centered on real GPS/GNSS measurements, navigation-aided processing, satellite-signal tracking support, and multipath path extraction. The public TrackChair description explicitly includes satellite and terrestrial navigation and positioning.
- `SECONDARY_TRACK = Signal Processing for Wireless Communications` — the paper also concerns acquisition/tracking support, delay--Doppler processing and signal-based path extraction; the public description includes acquisition, synchronization, localization/navigation, channel estimation and tracking.

This is a recommendation only. No track was selected in TrackChair and no submission was made.

### Submission keywords

`GNSS multipath; GPS L1 C/A; raw-IQ measurements; SAGE; delay--Doppler path extraction`

The manuscript and LaTeX keyword lines were reduced from six to five terms to follow the official IEEE Author Center's 3--5 keyword guidance. The portal's exact count/entry behavior remains unconfirmed.

## 5. Title audit

**Current title:** *SAGE-Based High-Resolution Multipath Characterization of GPS L1 C/A Signals in Dynamic Vehicular Environments*

`TITLE_STATUS = KEEP`

The title accurately names GPS L1 C/A, SAGE, multipath characterization and dynamic vehicular measurements. It does not claim a completed channel model, elevation statistics or a new SAGE estimator.

## 6. Local page and visual QA

The manuscript was compiled in an isolated temporary directory from the current `main.tex`, `references.bib` and figure PDFs using:

```text
pdflatex -> bibtex -> pdflatex -> pdflatex
```

All four commands returned exit code `0`. A minimal layout-only adjustment scales Figure 3 and Figure 4 to `0.92\textwidth`; it does not remove evidence or change scientific text. The resulting candidate is **4 pages**, which is within the CFP's five-page no-overlength target and avoids a fifth page containing only two references.

| Page | Visual check | Status |
|---:|---|---|
| 1 | Title, unresolved author block, abstract, keywords, two-column structure and Section I | **PASS with author gate open** |
| 2 | Table I, Section II/III text, equation and cross-column flow | **PASS** |
| 3 | Figure 1, Table II, Figure 2, representative path text and Section IV flow | **PASS** |
| 4 | Figures 3--4, captions, Conclusion and all references; no severe last-page blank region | **PASS** |

The previous 5-page rendering was visually inferior because page 5 contained only references [8]--[9]. It is retained only as an audit observation, not as the candidate PDF. No scientific result, figure, table, or Stage4 semantics were removed to obtain the four-page layout.

`PDF_VISUAL_QA_READY = YES`  
`LAST_PAGE_BALANCE = ACCEPTED_AFTER_MINIMAL_FIGURE_SCALING`

## 7. Local PDF technical QA

The isolated candidate PDF was checked with local Poppler tools:

| Check | Observed value | Status |
|---|---|---|
| Page count | 4 | **PASS within 5-page target** |
| Page size | US Letter, 612 x 792 pt | **Local PASS; VTC-specific size rule not confirmed** |
| Orientation | Portrait | **Local PASS** |
| Encryption | No | **PASS** |
| PDF version | 1.7 | **Local value; VTC-specific accepted version not confirmed** |
| File size | approximately 239 kB | **Local value; no VTC limit found** |
| Fonts | Embedded/subset according to `pdffonts` | **Local PASS** |
| Type 3 fonts | Present in imported figure/font resources | **Manual/PDF Checker review still required if VTC requests it** |
| Readability | `pdftotext` extraction succeeded | **PASS** |
| IEEE PDF eXpress/PDF Checker | Not run; VTC use is not confirmed | **OPEN** |

The local checks are not a substitute for VTC's authenticated upload validation or IEEE PDF eXpress/PDF Checker. No camera-ready-only copyright or final-paper metadata was added.

`PDF_TECHNICAL_QA_READY = NO`

## 8. Citation and reference QA

- `references.bib` contains 9 verified entries.
- The complete isolated compile chain returned zero errors/fatal errors, zero undefined citations and zero undefined references.
- BibTeX emitted zero warnings.
- No placeholder bibliography entry, duplicate citation key or orphan citation was observed in the final compile.
- The 9 entries are cited by the manuscript's Introduction, Measurement/Experimental Setup or Methodology sections; project-owned numerical results remain supported by the local evidence package rather than external citations.

`REFERENCES_READY = YES`  
`P14_REFERENCE_AUDIT = PASS`

## 9. Scientific freeze audit

The final manuscript continues to state only the frozen VTC scope: real dynamic GPS L1 C/A raw-IQ measurement, GNSS-SDR support, NAV-aided Stage0--Stage4 hierarchy, and bounded path-level characterization. It does not convert the five confirmed paths into a distribution, probability, environment-causal claim, LOW/MID/HIGH event-level statistic or completed channel model. Stage2 `L>=2`, Stage3 reliable centers and zero-event outputs retain their operational meanings. The raw-coarse/sampling/v3 work remains a negative acceleration investigation and is not a production method.

No new experiment, raw-IQ read, MATLAB/SAGE run, batch task, production request, scene artifact or result artifact was created by this audit.

## 10. Final readiness flags

```text
OFFICIAL_REQUIREMENTS_VERIFIED = NO
AUTHOR_VISIBILITY_RULE = NOT_CONFIRMED
AUTHOR_INFORMATION_REQUIRED = YES
AUTHOR_METADATA_INTEGRATED = NO
PRIMARY_TRACK_RECOMMENDATION = Positioning Technologies, Localization and Navigation
SECONDARY_TRACK_RECOMMENDATION = Signal Processing for Wireless Communications
TRACK_READY = YES (recommendation prepared; portal selection not performed)
PDF_VISUAL_QA_READY = YES
PDF_TECHNICAL_QA_READY = NO
VTC_SUBMISSION_CANDIDATE_READY = NO
NEXT_VTC_DECISION_REQUIRED = YES
```

### Remaining blockers

1. Confirm the initial-review author visibility rule in the authenticated TrackChair workflow or current conference instruction.
2. Supply real author metadata if author-visible, or remove identifying/placeholder metadata if anonymous review is confirmed.
3. Confirm the VTC-specific template, paper size, upload size, file format and PDF eXpress/PDF Checker requirement in the portal.
4. Re-run the final PDF technical check after author metadata and any required template/copyright instructions are applied.

The paper is not submitted by this audit.
