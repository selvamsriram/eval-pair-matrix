Agent 2’s job is **not** to redo the whole experiment. Its job is to answer one very specific reviewer-risk question:

> When the judge flags an answer that is “gold negative,” is the judge actually wrong, or did it find a different real source-grounding error?

This matters because Agent 1 found the new robust result on **target-negative flagging**: same-deployment judges flag target-negative answers less often. But “target-negative” only means the answer did **not** express the planted perturbation. It does **not** automatically mean the answer is fully correct.

The paper’s judge task asks the judge to flag **any factual error** against the original passages, while the gold label only tracks the **induced target error**—the planted perturbation. That mismatch is visible in the current protocol: the judge sees the answer and original passages, not the perturbation or gold label, and returns a factual-error flag plus wrong claim and supporting passage; the gold positive class is defined as an answer that entails the perturbed claim. 

## Simple example

Suppose the original passage says:

> League attendance rose **48%**.

The perturbed passage shown to the generator says:

> League attendance rose **35%**.

If the generator answer says “attendance rose **35%**,” then it contains the **target error**.

But imagine the answer does **not** mention 35%. Instead, it says something else unsupported, like “ticket sales increased by 93%,” and the judge flags that. Under the current induced-error gold label, that becomes a “false positive,” because the target error was absent. But from the judge’s actual task—detecting any source-grounding error—the judge may be right.

That is exactly what Agent 2 must separate.

# Agent 2’s technical task

Agent 2 should build a **human-review queue** from the existing JSONL files. It should not rerun models, relabel everything with another LLM, or modify raw data.

The queue should focus on the cases most likely to affect the new Agent 1 result:

```text
gold_has_induced_error = false
contains_factual_error = true
```

These are the current “false positives” under target-error scoring. But Agent 2 should rename them more carefully as:

```text
target-negative flagged cases
apparent false positives
```

because some may be legitimate alternate errors.

## What Agent 2 should output

The main output should be a CSV:

```text
paper/audit/fpr_review_queue.csv
```

Each row is one judge verdict that needs human review.

It should include:

```text
case_id
core_id
is_validated
generator
judge
pair_type
question
generator_answer
behavior_label
entails_original_claim
entails_perturbed_claim
gold_has_induced_error
contains_factual_error
original_value
perturbed_value
atomic_claim_original
atomic_claim_perturbed
wrong_claim
judge_explanation
supporting_source_passage_id
supporting_source_passage_text
modified_passage_ids
auto_target_match
auto_localization_match
human_target_present
human_judge_detected_target
human_alternate_valid_error
human_false_alarm
human_localization_correct
human_notes
```

The last six columns are for humans to fill.

Agent 2 should also produce:

```text
paper/audit/fpr_review_guide.md
paper/audit/fpr_review_summary.md
paper/tables/fpr_audit_summary.tex
```

# What cases should Agent 2 prioritize?

Order matters because you have limited time.

## Priority 1: same-deployment apparent false positives

These directly affect Agent 1’s new result.

Example pattern:

```text
generator = GPT
judge = GPT
gold_has_induced_error = false
contains_factual_error = true
validated = true
```

These answer the question:

> When the matching judge flags its own generator’s target-negative answer, is it a real false alarm or an alternate valid error?

## Priority 2: cross-deployment apparent false positives

Take an equal-size sample from cross-deployment cases.

Example:

```text
generator = GPT
judge = Grok or Gemini
gold_has_induced_error = false
contains_factual_error = true
validated = true
```

This tells us whether alternate-error detection happens more in cross-model judging than same-model judging.

That is crucial. If cross judges are flagging more because they are catching more real alternate errors, the “same judges over-flag less” result needs softer wording.

## Priority 3: all examples currently shown in the paper

Any example in the paper must be manually verified.

The current Table 7 false-positive example on page 12 is especially important. It has `Gold=False`, `Pred=True`, and the judge flags an ASC 842 / FASB / SEC issue. That may be an actual alternate grounding error, not a false alarm. 

## Priority 4: false negatives

These are:

```text
gold_has_induced_error = true
contains_factual_error = false
```

Sample about 30, balanced across GPT/Grok/Gemini generators. This checks whether missed target errors are truly misses or whether the gold label was too aggressive.

## Priority 5: sanity checks

Add a small sample of true positives and true negatives:

```text
15 TP
15 TN
```

This checks whether the audit instructions are understandable and whether the existing labels are broadly sane.

# What the human reviewer does

The human reviewer is the adjudicator. Agent 2 prepares the cases; the human decides what is actually true.

For each row, the human should answer five questions.

## 1. `human_target_present`

Question:

> Does the generator answer assert the induced perturbed claim?

Use the original/perturbed values and atomic claims.

Example:

```text
original_value = 48%
perturbed_value = 35%
answer says = 35%
```

Then:

```text
human_target_present = yes
```

If the answer avoids both 48% and 35%, then:

```text
human_target_present = no
```

If the answer mentions both, use:

```text
human_target_present = yes
```

but note `both claims` in `human_notes`.

## 2. `human_judge_detected_target`

Question:

> If the judge flagged an error, did the judge identify the induced target error?

This is about the judge’s `wrong_claim` and explanation.

If the induced target is “35% instead of 48%,” and the judge says “the answer incorrectly says 35%; the source says 48%,” then:

```text
human_judge_detected_target = yes
```

If the judge flags a different issue, then:

```text
human_judge_detected_target = no
```

## 3. `human_alternate_valid_error`

Question:

> If the answer did not contain the target error, did the judge identify another real error relative to the original passages?

This is the key field for Agent 2.

If the answer is target-negative but contains another unsupported or contradicted factual claim, and the judge correctly catches it:

```text
human_alternate_valid_error = yes
human_false_alarm = no
```

If the judge’s complaint is not actually supported by the passages:

```text
human_alternate_valid_error = no
human_false_alarm = yes
```

## 4. `human_false_alarm`

Question:

> Was the judge actually wrong to flag this answer?

Use this only after checking both target and alternate errors.

For target-negative flagged cases:

```text
human_false_alarm = yes
```

means:

> The answer did not contain the induced target error, and the judge did not identify any other valid source-grounding error.

```text
human_false_alarm = no
```

means:

> The judge found either the target error or another real error.

## 5. `human_localization_correct`

Question:

> Did the judge cite the right source passage?

For target errors, the cited passage should usually be one of the original passages corresponding to the modified passage IDs.

For alternate errors, the cited passage should be the passage that actually supports the human’s judgment.

# The important distinction

There are two different evaluations:

## Target-error evaluation

This asks:

> Did the judge detect the planted perturbation?

Here, alternate errors are not the target. So a judge that finds some other error is not detecting the planted perturbation.

## Any-error evaluation

This asks:

> Did the judge correctly find any factual/source-grounding problem?

Here, alternate errors count as valid.

The current paper mixes these two. Agent 2’s job is to untangle them.

# How Agent 2’s results affect the paper

After human review, you will have counts like this:

```text
same-deployment target-negative flagged cases:
  real false alarms: X
  alternate valid errors: Y
  unclear: Z

cross-deployment target-negative flagged cases:
  real false alarms: A
  alternate valid errors: B
  unclear: C
```

Then the paper can say one of three things.

## Case A: most apparent FPs are real false alarms

Then the result is strong:

> Same-deployment judges show no recall leniency on target errors, but they produce fewer false alarms on their own generator’s target-negative answers.

## Case B: many apparent FPs are alternate valid errors, but same/cross rates are similar

Then say:

> Under the induced-target label, same-deployment judges flag target-negative answers less often. Manual audit shows that some apparent false positives are alternate valid errors, but this issue affects same- and cross-deployment cases similarly.

## Case C: cross judges flag more because they catch more alternate valid errors

Then soften the claim:

> The target-error recall result is robustly null. The apparent FPR gap should be interpreted as a target-negative flag-rate difference, partly affected by the mismatch between target-error labels and any-error judge prompts.

Case C is not a disaster. It becomes a methodological contribution.

# What the human should not do

Do not try to relabel all 2,683 verdicts manually.

Do not rewrite the scientific claim case by case while reviewing.

Do not judge based on outside knowledge. Use the provided original passages as the reference.

Do not let the agent decide final human labels for ambiguous cases.

Do not call the audit “human annotation” unless there are independent annotators. If only you review it, call it:

```text
targeted author audit
manual adjudication sample
```

# Minimal version under time pressure

Given two days, the minimum acceptable Agent 2 package is:

```text
1. All same-deployment validated apparent FPs reviewed.
2. Equal-size cross-deployment validated apparent FP sample reviewed.
3. All paper examples reviewed.
4. 30 false negatives reviewed.
5. Short summary table added to paper.
```

The summary table can be simple:

```text
Audit subset | n | target error | alternate valid error | false alarm | unclear
Same-deployment target-negative flagged | ... | ... | ... | ... | ...
Cross-deployment target-negative flagged | ... | ... | ... | ... | ...
False negatives | ... | ... | ... | ... | ...
```

# Copy-paste prompt for Agent 2

```text
You are the FPR / target-negative audit agent for the Eval-Pair Matrix GroundLM revision.

Agent 1 found no robust same-deployment effect on target-error recall, but did find lower target-negative flagging for same-deployment judges. The main threat is that the gold label tracks only the induced target error, while the judge prompt asks about any factual error. Therefore, some apparent false positives may be alternate valid source-grounding errors.

Do not rerun models and do not modify raw data.

Build paper/audit/fpr_review_queue.csv over validated records only. Include:
1. all same-deployment target-negative flagged cases;
2. an equal-size sample of cross-deployment target-negative flagged cases;
3. all examples currently used in the paper;
4. 30 false negatives balanced across generators;
5. 15 true positives and 15 true negatives as sanity checks.

For each row include:
case_id, core_id, generator, judge, pair_type, question, generator_answer, behavior_label, entails_original_claim, entails_perturbed_claim, gold_has_induced_error, contains_factual_error, original_value, perturbed_value, atomic_claim_original, atomic_claim_perturbed, wrong_claim, judge_explanation, supporting_source_passage_id, supporting_source_passage_text, modified_passage_ids, auto_target_match, auto_localization_match.

Add blank human columns:
human_target_present, human_judge_detected_target, human_alternate_valid_error, human_false_alarm, human_localization_correct, human_notes.

Also write paper/audit/fpr_review_guide.md explaining the labels and paper/audit/fpr_review_summary.md with counts by subset after human labels are filled. Produce paper/tables/fpr_audit_summary.tex if human labels exist.
```

The main idea: **Agent 2 prepares the evidence; the human decides whether the judge was actually wrong.**
