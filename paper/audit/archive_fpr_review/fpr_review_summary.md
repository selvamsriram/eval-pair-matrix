# FPR / target-negative audit summary

_Targeted author audit (manual adjudication sample). Auto-generated from `fpr_review_progress.json`._

Progress: **33 / 184** cases reviewed.

| Audit subset | n | reviewed | target error | alternate valid | artifact | false alarm | unclear |
|---|---|---|---|---|---|---|---|
| Same-deployment target-negative flagged | 60 | 11 | 10 | 1 | 0 | 0 | 0 |
| Cross-deployment target-negative flagged | 61 | 0 | 0 | 0 | 0 | 0 | 0 |
| False negatives | 31 | 0 | 0 | 0 | 0 | 0 | 0 |
| Sanity TP | 16 | 12 | 12 | 0 | 0 | 0 | 0 |
| Sanity TN | 16 | 10 | 0 | 0 | 0 | 0 | 10 |

**Bucketing** (precedence): a reviewed flag is *target error* if the judge identified the planted error; else *alternate valid* if it caught a different real error; else *artifact* if it flagged a meta-claim about the passages (refusal/perturbation artifact); else *false alarm* if a genuine false alarm; else *unclear*.

**Tentative interpretation:** Pending — review more apparent-FP cases (need roughly half of each group) before deciding Case A/B/C.

For false negatives, `target error` here counts cases the human still judged as a genuine miss; use `human_target_present=no` in notes to flag gold that was too aggressive.
