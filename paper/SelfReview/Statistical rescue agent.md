Statistical rescue agent
Goal

Produce a new audit layer that fixes the central same-model confound using existing data only.

Files to inspect first
paper/audit/raw_data_audit.py
data/exp/3provider_300.jsonl
all three 05_label_eval.jsonl files
all nine 06_judge.jsonl files
paper/audit/audit_report.json

The current report confirms 275 validated records, 25 gap-fill records, 83/92/125 selected perturber counts, 897 label-eval rows, 2,683 verdicts, and only two observed pair types: same_exact_model and cross_provider_family.

Agent task

Create:

paper/audit/paired_audit.py
paper/audit/paired_audit_report.json
paper/audit/paired_audit_summary.md
paper/tables/paired_effects.tex
paper/tables/validated_matrix.tex

The script should be read-only over raw JSONL.

Required analyses

First, make validated-only primary:

primary_set = records where all five validation gates pass
diagnostic_set = failed-validation/gap-fill records

The code already has a passes(record) helper in raw_data_audit.py; reuse or centralize it.

Second, flatten each judge verdict into a table with:

core_id
is_validated
generator_provider
generator_model
generator_sample_id
judge_provider
judge_model
pair_type
gold_has_induced_error
contains_factual_error
verdict
wrong_claim
supporting_source_passage_id
modified_passage_ids
perturbation_type
behavior_label from label_eval if joinable

Third, compute the answer-paired effect. For each generator answer, compare the matching judge to the nonmatching judges on the same answer:

same_pred = prediction by judge matching the generator
cross_pred_mean = mean prediction by the two nonmatching judges
paired_delta = same_pred - cross_pred_mean

Do this separately for:

gold-positive answers -> paired recall delta
gold-negative answers -> paired false-positive-rate delta
all answers -> paired flag-rate delta

This is the crucial fix. It directly addresses the earlier objection that GPT/Grok/Gemini outputs have different difficulty.

Fourth, cluster-bootstrap by core_id:

sample core_id with replacement
include all generator answers and all available judge verdicts for sampled core_ids
recompute paired deltas
repeat 5,000 or 10,000 times
report percentile 95% CI

Fifth, output these tables:

A. Validated-only 3x3 matrix: n, TP, FP, FN, TN, precision, recall, F1
B. Full 300-record matrix as appendix/sensitivity
C. Paired same-deployment effect:
   - recall delta with CI
   - FPR delta with CI
   - flag-rate delta with CI
D. Judge-specific exploratory paired deltas:
   - GPT-on-GPT vs other judges on GPT answers
   - Grok-on-Grok vs other judges on Grok answers
   - Gemini-on-Gemini vs other judges on Gemini answers
E. Gap-fill diagnostic comparison