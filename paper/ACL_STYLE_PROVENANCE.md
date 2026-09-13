# Official ACL style provenance

The active `acl.sty` and `acl_natbib.bst` are unmodified files from
[acl-org/acl-style-files](https://github.com/acl-org/acl-style-files), downloaded
on September 12, 2026 at commit
`d5adc823ff0f80f98c80405ca0ab66c68e684409`.

| File | SHA-256 |
|---|---|
| `acl.sty` | `19dfeddc2c0e448f3926a0bef048a9db3f3611b46265b760caabd7ada4f361de` |
| `acl_natbib.bst` | `6fbb306202290f4b68e74ac1460a8b27398500cb6dfeb4492e74c457eae7cd1e` |

The upstream README, formatting guidance, pdfLaTeX and LuaLaTeX templates, and
sample bibliographies are in `docs/acl-template/` at the repository root. They are also copied without edits
from that commit. To compile an example template, copy it and its sample
bibliography into this directory so that it can find the active style files.

`camera_ready.tex` uses `\documentclass[11pt]{article}` and
`\usepackage[final]{acl}`. It does not override the style's geometry, body fonts,
line spacing, title-box dimensions, caption size, or page-number policy.
The paper's bibliography remains a manual `thebibliography` list rendered by
the official style; `acl_natbib.bst` is available for a future BibTeX conversion.

The previous `acl.sty` was a custom minimal replacement. Its prior contents
remain recoverable from Git history. The original submitted PDF is preserved
as `archive/submissions/original/paper.pdf`; it is not a build of the updated style.
