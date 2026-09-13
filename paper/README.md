# Paper sources and build

`camera_ready.tex` is the final entry point. It uses the unmodified official ACL
style and the authors' names, affiliation, and email addresses. The camera-ready
submission has eight main-text pages and 16 pages total.

The [submitted PDF](../output/pdf/eval-pair-matrix-camera-ready.pdf),
[yellow-only comparison](../output/pdf/eval-pair-matrix-all-changes.pdf), and
[release ZIPs](../output/release/) are frozen. See the
[submission record](../docs/submission.md) for the Git tag and hashes.

## Build

From the repository root, with Python 3 and pdfLaTeX:

```bash
bash paper/build_camera_ready.sh
```

The build checks official style hashes, compiles three passes, and rejects
unresolved-reference warnings and overflowing text. It writes
`tmp/pdfs/camera-ready/eval-pair-matrix-camera-ready.pdf` and keeps intermediates
in the same ignored directory. It does not replace the submitted PDF.

## Files

- `main_body.tex`, `references.tex`, `appendix_content.tex`: submitted content.
- `figures/`: the ten referenced PDFs and three existing Graphviz sources.
- `tables/`: the published sensitivity table and its numerical report.
- [ACL style provenance](ACL_STYLE_PROVENANCE.md): official commit and hashes;
  upstream examples are in [docs/acl-template](../docs/acl-template/).
- [Reproducibility guide](REPRODUCIBILITY.md): analysis commands and expected results.
- [audit/](audit/README.md): saved numerical reports, human-review inputs, and usage ledger.
- `reference_metadata_check.json`: source verification of the cited works.
- `generate_composition_figure.py`: data-derived composition plots; writes into
  `tmp/figures/composition/` and is not part of the paper build. Final PDFs are frozen.

## Rebuild the comparison or packages

```bash
python3 paper/build_review.py
python3 paper/package_camera_ready.py
```

The comparison requires `pdfplumber`, `pypdf`, and pdfLaTeX. It uses original
submission commit `1554258`, checks every glyph against the preserved clean
PDF, and writes a yellow-only copy plus change manifest and source patch to
`tmp/pdfs/yellow-only/`. Deletions and layout-only changes remain in the patch.

Packaging writes current-source and reproducibility ZIPs, each with a SHA-256
manifest, to `tmp/release/`. The pre-cleanup submission ZIPs under `output/release/`
remain byte-identical to the submission snapshot.

[Review history](../archive/camera-ready/README.md),
[older submission wrappers](../archive/submissions/README.md), and
[figure development](../archive/figure-development/README.md) are archived.
Historical wrappers require their original Git checkout to reproduce old PDFs.
