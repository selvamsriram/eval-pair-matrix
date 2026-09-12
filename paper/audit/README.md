# Canonical audit entry points

Use [../REPRODUCIBILITY.md](../REPRODUCIBILITY.md) for the final analysis commands
and expected outputs, and the camera-ready paper for the accepted interpretation.

- `paired_audit.py`, `paired_audit_report.json`, and `paired_verdicts.csv` implement
  and record the answer-paired analysis.
- `behavior_stratified.py` and its JSON report provide the behavior breakdown.
- `cell_review_queue.json` / `.csv` are the frozen seed-fixed, stratified queue;
  `cell_review_progress.json` contains the human decisions. Appendix D.1 supplies
  the codebook. There are 88 completed verdict cases out of 153, covering 79
  answers and 70 records. The 25 reviewed apparent-FP cases cover 25 answers from
  22 records: 22 alternate source errors, two adoption-label mistakes, one unclear.
- `judge_cost.py`, `judge_usage.jsonl`, and `judge_usage_manifest.json` reproduce
  recorded judge-call usage without the private local trace files.

The targeted audit shows why an adoption-negative flag is not automatically a
false alarm. It does not establish the cause of the −4.3-point paired flagging
gap or estimate population false-alarm prevalence. Completed decisions and raw
measurements are unchanged.

Older narrative reports (`paired_audit_summary.md`, `audit_dossier.md`, and
`archive_fpr_review/`) record earlier interpretations. They are historical, not
the camera-ready narrative. Regenerating their scripts may reproduce those old
wordings. The numerical reports and frozen audit inputs above are canonical.
