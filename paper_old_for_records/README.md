# Eval-Pair Matrix ACL final revision

This bundle includes the revised ACL manuscript, raw-data audit artifacts, extracted examples, and figure sources.

The manuscript is a single source, `eval_pair_matrix_acl_final_revision.tex`, that builds two
versions via a flag (see the build-mode block at the top of the file):

- **preprint** (arXiv): named authors, no line numbers — the default build.
- **review** (ACL submission): anonymous (`Anonymous ACL submission`), with line numbers.

Build:
```bash
make            # builds both versions
make preprint   # arXiv/camera-ready -> eval_pair_matrix_acl_final_revision_preprint.pdf
make review     # anonymous ACL submission -> eval_pair_matrix_acl_final_revision_review.pdf
```

Without the Makefile, the review version is built by defining `\submissionmode`:
```bash
latexmk -pdf eval_pair_matrix_acl_final_revision.tex                          # preprint
latexmk -pdf -usepretex='\def\submissionmode{}' \
        -jobname=eval_pair_matrix_acl_final_revision_review \
        eval_pair_matrix_acl_final_revision.tex                               # review
```

Paper numbers are derived from `audit/audit_report.json`; examples are drawn from `audit/examples_report.json`.
