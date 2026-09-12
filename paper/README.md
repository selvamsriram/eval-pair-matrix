# Eval-Pair Matrix camera-ready paper

The final manuscript entry point is `camera_ready.tex`, using the unmodified
official ACL style with Sriram Selvam and Anneswa Ghosh as authors.

From the repository root:

```bash
bash paper/build_camera_ready.sh
```

Requires Python 3 and a TeX installation with pdfLaTeX. The script verifies
official style hashes, compiles three times, rejects unresolved-reference
warnings and overflowing text, and writes
`output/pdf/eval-pair-matrix-camera-ready.pdf`. The paper has eight main-text
pages and 16 pages total. Intermediates stay under `tmp/pdfs/camera-ready/`.

- `main_body.tex`, `references.tex`, `appendix_content.tex`: canonical shared sources.
- `figures/`: vector figures used in the paper; existing figure data are unchanged.
- `ACL_STYLE_PROVENANCE.md`: pinned upstream commit and hashes.
- `CAMERA_READY_STATUS.md`: completed checks and remaining external submission steps.
- `REPRODUCIBILITY.md`: saved-data analysis commands, expected outputs, and artifact contents.
- `audit/`: frozen human-review inputs, numerical outputs, analysis scripts, and portable usage ledger.
- `reference_metadata_check.json`: primary-source verification of the 24 cited works.

For the complete comparison against the original submission, run
`python3 paper/review/build_full_review.py`. It writes
`output/pdf/eval-pair-matrix-all-changes.pdf`, showing the final paper with changed or added
text highlighted in yellow. This is the author review copy; submit the clean PDF.

`python3 paper/package_camera_ready.py` produces the final source and
reproducibility ZIPs under `output/release/`, with file hashes. Archives contain
only the explicitly selected release files; local packaging is not a Git push.

`acl_submission.pdf` is the preserved original anonymous submission, not the
final version. Historical anonymous/preprint wrappers share the now-updated
sources; rebuilding them would not reproduce their historical PDFs. The original
source baseline is commit `1554258`; the complete comparison builder uses it.
