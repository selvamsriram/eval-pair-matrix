# Camera-ready production status

Updated September 12, 2026. All selected revisions are applied. Local manuscript,
comparison, reproducibility, and package preparation are complete. The clean PDF
is the submission file; the highlighted PDF is for author review.

## Final outputs

- `output/pdf/eval-pair-matrix-camera-ready.pdf`: 16 pages; main text and artifact
  statement end on page 8; Limitations/Ethics/References start on page 9;
  Appendix starts on page 11.
- `output/pdf/eval-pair-matrix-all-changes.pdf`: the same 16 final pages with
  changed/added text highlighted in yellow against the original submission.
  No old wording, arrows, guide, headers, or extra pages; clean layout preserved.
- `output/release/eval-pair-matrix-camera-ready-source.zip`: final LaTeX source,
  official style files, and all referenced figures/tables.
- `output/release/eval-pair-matrix-reproducibility.zip`: final source, canonical
  data, analysis scripts/reports, human-review inputs, prompts/schemas, and
  portable usage ledger. Each ZIP has an internal SHA-256 manifest.

Paths above are relative to the repository root. Build and packaging commands
are in `README.md` and `REPRODUCIBILITY.md` in this directory.

## Selected reviewer revisions

| Item | Final state |
|---|---|
| 1. Central claim scope | Four minimal replacements integrated; measured aggregate contrast retained |
| 2. Audit interpretation | Approved interpretation, queue/coverage descriptions, and caption correction integrated; −4.3 pp and audit judgments unchanged |
| 3. Label reporting / new sensitivities | Reporting corrected in the final targeted pass; new sensitivity analyses remain skipped |
| 4. Endpoint heterogeneity | Existing GPT −3.8 / Grok −3.7 / Gemini +6.0 pp estimates foregrounded as exploratory; conclusion aligned |
| 5. Independent second audit | Skipped by author decision |
| 6. Computational cost | Main-text scaling paragraph and appendix usage table integrated |
| 7. Smaller/local models | Brief limitation states that generalization beyond the three proprietary endpoints is untested, followed by protocol controls |
| 8. Further version/reference work | Skipped; earlier reference checks/corrections retained |
| 9. Artifact consistency and production | Local documentation, cost inputs, reproduced results, PDF QA, and packages completed |

No new model calls, human decisions, or declined sensitivity analyses were
introduced. The abstract was shortened during the original ACL-formatting pass;
the latest author-requested pass adds an aggregate/three-endpoint qualifier.
Existing result estimates and figure data are preserved.

## Final targeted corrections

The authors explicitly requested eight minimal corrections after the initial
production pass. `review/targeted_corrections.json` records the exact replacements:
Primary/prespecified terminology (two edits), 896 nonempty answers, 897 labeled
slots with four deterministic empty-generation labels, the entailment/behavior
rule and fallback for three unlabeled answers, the abstract endpoint qualifier,
a non-equivalence sentence, and the revised local-model limitation. No estimates,
raw data, appendix, reference entries, or style files changed. The table-export
script now also says Primary. The main-text budget remains eight pages.

## Production verification

- Official `acl.sty` and `acl_natbib.bst` match upstream commit
  `d5adc823ff0f80f98c80405ca0ab66c68e684409` byte for byte. The build checks hashes.
- A4, 11-point official final ACL wrapper; supplied names, affiliation and emails;
  final PDF metadata; no line numbers, page numbers, or review markup in the clean PDF.
- Three-pass pdfLaTeX build: no unresolved citations/references, LaTeX/package
  warnings, or overfull boxes. Ordinary underfull diagnostics do not overflow.
- All fonts are embedded and no Type 3 fonts occur in either deliverable.
- All 16 clean pages and 16 highlighted pages were rendered and visually checked;
  no clipping, overlap, missing glyphs, or unresolved references were observed.
- ACL PubCheck commit `237bee3a554f2d2fcda69cd0cf1edf4168e3d339` reports
  **All Clear!** on the final clean PDF with `--paper_type long
  --disable_name_check`; bottom-margin checks remain enabled. Reference
  existence/title/author checks were performed separately against primary
  records. The PDF was not sent to an external reference-extraction service.
- Original PDF preserved: SHA-256
  `f481908bb3a734f038605f655a4d014a2bd57a35a76bb67fb264a39d39373dac`.
  Rebuilding original commit `1554258` produces exactly the original submitted
  PDF's extracted layout text, establishing the comparison baseline.
- The clean PDF has the requested GitHub artifact URL and no anonymous artifact
  URL. Reference-title links are embedded and valid PDF annotations.

## Artifact verification

The root README now distinguishes the final `3provider_300` 83/92/125 pool from
the historical 100/100/100 pool and documents the implemented generator/judge
steps. `REPRODUCIBILITY.md` and `audit/README.md` identify canonical analyses and
separate historical narrative reports from the accepted interpretation.

In an isolated tree, saved inputs reproduced the paired report/flattened verdict
CSV, behavior report, existing sensitivity JSON values/table, and human-review
queue. The sensitivity JSON differs only in its terminal newline. The original
manuscript tables and raw data were not overwritten. NumPy 2.3.5 is recorded in
`requirements-analysis.txt`.

The usage-only ledger contains all 2,688 events, including five failures, and
reproduces the raw-trace report byte for byte: 5,626,958 input tokens, 308,181
output tokens, and 17,580,271 ms (4.883408611 hours) summed call time. Original
trace hashes are retained; prompts/responses/exception bodies are omitted.

## External submission steps

Official requirements were rechecked at
[GroundLM regular-paper camera-ready instructions](https://groundlm.github.io/grouplm_emnlp2026/camera-ready.html#regular-papers)
on September 12, 2026. The page states a September 12 AoE deadline and directs
regular papers to the relevant OpenReview venue. Use regular **Track 1**.
It does not explicitly grant extra main-text pages; this PDF retains eight.
Separate system-paper BibTeX uploads and shared-task citations do not apply here.

- The supplied repository URL still returns HTTP 404 without authentication.
  Publication/visibility has not been changed. The authors were asked to confirm
  public release or an alternative accessible URL; no response is recorded yet.
- No acknowledgment/funding/conflict wording was supplied. The authors were asked
  whether any such wording applies; none has been invented.
- No Git push, repository publication, portal metadata update, or submission
  upload has been performed. Submit the clean PDF after resolving the applicable
  external items; the highlighted PDF is a review aid, not the submission file.
