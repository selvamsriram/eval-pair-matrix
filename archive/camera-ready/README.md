# Camera-ready revision history

The final paper has been submitted. This directory preserves the review process:

- [CAMERA_READY_PLAN.md](CAMERA_READY_PLAN.md): triage and author decisions.
- [CAMERA_READY_STATUS.md](CAMERA_READY_STATUS.md): final production checklist as
  recorded before submission; later author confirmation supersedes pending upload.
- `review/*_changes.json` and `review/targeted_corrections.json`: proposal/edit records.
- [review/all_changes.json](review/all_changes.json): final source differences,
  highlight counts, and verified PDF hashes.
- [review/submitted-to-camera-ready.patch](review/submitted-to-camera-ready.patch):
  complete shared-source diff against original commit `1554258`.
- `pdf/`: intermediate claim, audit, heterogeneity, cost, and local-model review PDFs.
- `review/build_claim_review.py`: historical proposal renderer; its anchors refer
  to earlier source revisions. Replay from the relevant historical Git checkout.

The archived `review/README.md` is preserved verbatim, so its old command paths
are historical. Current commands are in [paper/README.md](../../paper/README.md).
The active complete comparison builder is `paper/build_review.py`; it writes
only to `tmp/pdfs/yellow-only/`. The accepted cost report now lives at
`paper/audit/judge_cost_summary.json` beside its reproduction script and ledger.

The frozen final review PDF remains at
[output/pdf/eval-pair-matrix-all-changes.pdf](../../output/pdf/eval-pair-matrix-all-changes.pdf).
