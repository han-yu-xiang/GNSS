# VTC2027-Spring Submission Requirements

Audit date: 2026-08-14 (Asia/Shanghai)

## Official VTC sources

| Item | Confirmed information | Official source |
|---|---|---|
| Regular paper deadline | 1 September 2026 | https://events.vtsociety.org/vtc2027-spring/call-for-papers-2/ |
| Acceptance notification | 20 December 2026 | Same CFP page |
| Paper revision deadline | 15 March 2027 | Same CFP page |
| Submission type | 5-page, original, unpublished full paper | Same CFP page |
| Standard length | Five pages without overlength charge | Same CFP page |
| Maximum accepted length | Up to seven pages; up to two additional pages with page charges | Same CFP page |
| Review submission ceiling | The CFP advises not submitting more than eight pages for review | Same CFP page |
| Additional-page charge | USD 100 per additional page, as stated on the current CFP page | Same CFP page |
| Submission system | Public VTC2027-Spring TrackChair page is reachable and exposes Submit paper links; no account was used and no submission was attempted | https://vtc2027spring.trackchair.com/ |
| Relevant tracks | Antenna Systems, Propagation, and RF Design; Positioning Technologies, Localization and Navigation; Signal Processing for Wireless Communications | Same CFP page and TrackChair page |

The five-page target remains the project’s internal submission rule. The two-page overlength option is recorded for compliance planning, not selected as the target.

## Template decision

No VTC2027-Spring-specific LaTeX template was identified on the official CFP or public TrackChair pages during this audit. The official CFP links final-paper guidance but does not publish a VTC-specific class. The workspace therefore uses the current generic IEEE conference LaTeX convention:

```latex
\documentclass[conference]{IEEEtran}
```

Official IEEE template guidance:

- IEEE Author Center Conferences: https://conferences.ieeeauthorcenter.ieee.org/write-your-paper/authoring-tools-and-templates/
- IEEE conference template page: https://www.ieee.org/conferences/publishing/templates.html
- Official IEEE conference LaTeX package URL recorded by the IEEE template ecosystem: https://www.ieee.org/content/dam/ieee-org/ieee/web/org/pubs/conference-latex-template_10-17-19.zip
- Official IEEE conference bibliography package URL: https://www.ieee.org/content/dam/ieee-org/ieee/web/org/conferences/IEEEtranBST2.zip

The official IEEE Author Center recommends IEEE conference templates in Word or LaTeX and provides LaTeX validation resources. The source page was reachable through the official Author Center, while the legacy IEEE template page itself returned no downloadable content in the current sandbox session. The package URL is retained for manual verification/download by the project owner.

## Local template status

- `manuscript/latex/main.tex`: independent conference manuscript skeleton created.
- `manuscript/latex/references.bib`: created; no unverified literature metadata was invented.
- `manuscript/latex/template_reference/`: reserved for the untouched official package and extraction receipt.
- Local TeX executables and `IEEEtran.cls`: not found during read-only audit.
- Local PDF compilation: not attempted because the required toolchain is absent.

## Submission checks still required

1. Obtain and preserve the current official IEEE conference package in `manuscript/latex/template_reference/`.
2. Compile locally or in an approved offline LaTeX environment.
3. Check page count, references, figure fonts, overflow and missing labels.
4. Validate the final PDF with the IEEE-provided validation route when the manuscript is ready.
5. Submit through the official VTC2027-Spring TrackChair system only after author metadata and scientific QA are complete.
