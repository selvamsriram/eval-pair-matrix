# Repository guide

Run commands from the repository root. The root README links the paper and the
shortest reproduction path; [cli.md](cli.md) contains the full CLI guide.

## Current work

- `src/perturb/`: runtime code, prompts, schemas, providers, and viewer.
- `data/exp/3provider_300.jsonl`: final frozen pool and adjacent manifest.
- `data/runs/` and `data/traces/`: recorded runs at their original paths.
  Canonical inputs are inventoried by `paper/audit/paired_audit_report.json`.
  Earlier runs remain available for provenance; filenames alone do not identify
  the final experiment. Raw traces are not included in the release ZIPs.
- `paper/`: final manuscript, referenced figures, published table, audit inputs,
  numerical reports, and build/package scripts. See [paper guide](../paper/README.md).
- `output/pdf/`: exact submitted paper and final highlighted review copy.
- `output/release/`: frozen submission archives, hashes, and production checks.
- `docs/`: submission record, CLI guide, and official ACL template examples.
- `archive/`: historical research materials, indexed in [archive/README.md](../archive/README.md).

## Generated files

Paper and comparison builds write into `tmp/pdfs/`; packaging writes into
`tmp/release/`. Both are ignored by Git. The paired analysis writes its legacy
narrative summary into `tmp/analysis/`; numerical reports remain at their existing
paths. Additional LaTeX exports that are not used by the manuscript are ignored.

Tracked final PDFs, figures, published tables, and submitted ZIPs are deliberate
snapshots. Rebuilding should not overwrite `output/`. Human audit decisions in
`paper/audit/cell_review_progress.json` are frozen inputs.

Credentials, virtual environments, caches, and local traces retain their
existing ignore rules. Some selected historical data runs and traces are
already tracked; this cleanup does not relocate or remove them.

## Cleanup provenance

Tag `camera-ready-submitted-2026-09-12` points to commit `ab9cfba`, before the
cleanup. [Submission hashes](submission-manifest.json) identify preserved files.
[Cleanup manifest](../archive/cleanup-manifest.json) records file moves and removals.
[Cleanup verification](cleanup-verification.json) records the rebuild, preservation,
and packaged-analysis checks.
Only regenerable LaTeX intermediates and one verified duplicate original PDF
were removed. Git history retains their original bytes.

Historical scripts and wrappers are records of earlier work. Their old paths
and narrative interpretations may no longer apply. Replay them from the stated
historical commit rather than running them against the submitted artifacts.
