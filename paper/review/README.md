# Complete original-to-camera-ready comparison

All selected wording revisions (items 1, 2, 4, 6 and 7) are accepted and applied.
The clean output is `output/pdf/eval-pair-matrix-camera-ready.pdf`.

Rebuild the complete comparison from the repository root:

```bash
python3 paper/review/build_full_review.py
```

This writes `output/pdf/eval-pair-matrix-all-changes.pdf`: the exact 16-page
final camera-ready PDF with changed or added wording highlighted in yellow.
There is no old text, arrow, extra cover, comparison header, or page number.
Newly linked reference titles are yellow because their links are new.

The builder requires `pdfplumber` and `pypdf` as well as pdfLaTeX. It compiles a
temporary color-marked source to identify the changed glyphs, verifies every
glyph against the clean PDF (text and position), then adds yellow backgrounds
directly to a copy of the clean PDF. It does not reflow or replace the final
paper's contents. Deletions and layout-only changes have no final text to
highlight; they remain recorded in the source patch.

The original baseline is commit `1554258` (`Final revision of paper`). Rebuilding
its anonymous wrapper, style, shared sources, references and unchanged figures
produced exactly the same `pdftotext -layout` output as the supplied submission.
The original PDF has SHA-256
`f481908bb3a734f038605f655a4d014a2bd57a35a76bb67fb264a39d39373dac`.
It remains unmodified. `all_changes.json` records the source changes, highlight counts, and PDF hashes;
`submitted-to-camera-ready.patch` records every shared-source diff, including
layout-only lines. Added author details are highlighted. Wrapper/style changes remain in the
production record, without additional pages in the highlighted PDF.

The highlights include the earlier abstract shortening, author details, repository
URL, reference links and restored coauthor, and all approved wording revisions.
The final official ACL layout is retained exactly. The latest author-requested corrections add an aggregate/three-endpoint qualifier
to the abstract and minimal label/count/limitation clarifications. Exact edits
are in `targeted_corrections.json`. Declined analyses were not added.

Individual proposal JSONs preserve the accepted changes from earlier steps.
Their old anchors no longer match the final sources; their PDF outputs are
historical. Use the complete comparison above for the final review.

`judge_cost_summary.json` is the accepted cost report. The portable reproduction
command is `python3 paper/audit/judge_cost.py`; the usage ledger and source hashes
are in `paper/audit/`. It matches the original raw-trace report exactly.
