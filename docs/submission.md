# Submitted camera-ready snapshot

The authors confirmed submission to GroundLM 2026 after the final camera-ready
corrections. The preserved repository snapshot is:

- Tag: `camera-ready-submitted-2026-09-12`
- Commit: `ab9cfba` — Finalize GroundLM camera-ready paper and preserve review artifacts
- Original anonymous submission baseline: `1554258`

## Preserved artifacts

- [Submitted paper](../output/pdf/eval-pair-matrix-camera-ready.pdf): 16 pages,
  with main text through page 8.
- [Yellow-only comparison](../output/pdf/eval-pair-matrix-all-changes.pdf): the same
  final pages, with changed or added text highlighted against the original submission.
- [Source archive](../output/release/eval-pair-matrix-camera-ready-source.zip)
- [Reproducibility archive](../output/release/eval-pair-matrix-reproducibility.zip)
- [Release manifest](../output/release/release-manifest.json)
- [Final production verification](../output/release/verification.json)

[submission-manifest.json](submission-manifest.json) records SHA-256 hashes for
these artifacts and the manuscript, referenced figures/table, canonical analysis
inputs/results, human decisions, and usage ledger. They are preserved through
repository cleanup. The release ZIPs contain the pre-cleanup layout exactly.

The final production pass reported ACLPubCheck **All Clear!**, embedded fonts,
no Type 3 fonts, and no unresolved-reference or overflow warnings. These are
recorded checks from the submission pass. New build commands write to `tmp/`.

## Historical records

[Original submission](../archive/submissions/original/paper.pdf),
[OpenReview reviews](../archive/reviews/openreview.pdf), and the
[camera-ready revision history](../archive/camera-ready/README.md) are preserved.
The archived production checklist describes the state before submission;
the authors' later confirmation above supersedes its pending-upload entry.

See [paper/README.md](../paper/README.md) to build and
[paper/REPRODUCIBILITY.md](../paper/REPRODUCIBILITY.md) to reproduce results.
