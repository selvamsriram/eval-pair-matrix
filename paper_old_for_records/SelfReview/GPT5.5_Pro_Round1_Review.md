# Revised verdict

After rereading the full 15-page PDF—including the appendices, confusion counts, perturbation breakdowns, and example errors—my assessment is:

**Strong GroundLM fit, but I would not submit the archival version unchanged.** The main problem is deeper than missing confidence intervals: the current diagonal-versus-off-diagonal calculation does not cleanly identify same-model bias. Fortunately, most of the necessary correction can be done using the existing 2,683 verdicts. 

GroundLM is an unusually appropriate venue: it explicitly solicits RAG, factuality, hallucination, grounding-evaluation frameworks, benchmarks, and negative results. The direct-submission deadline is June 29, 2026 AoE, with eight content pages for an archival long paper. ([GroundLM][1])

## The central reviewer objection

The paper currently calculates each judge’s “same-model signature” by comparing that judge’s diagonal cell against its scores on answers from the other generators. But those are **different answers with different styles, refusal rates, lengths, behaviors, and difficulty**.

One revealing comparison from the published matrix:

* GPT judge recall on GPT outputs: **77.5%**
* Grok judge recall on those GPT outputs: **77.7%**
* Gemini judge recall on those GPT outputs: **86.3%**

Therefore, the GPT judge is not visibly unique in missing GPT-generated errors: Grok misses almost exactly as many on that answer set. The claimed −6.2-point GPT “self-leniency” comes from comparing GPT’s performance on GPT answers with GPT’s performance on different Grok and Gemini answers—not from comparing GPT with other judges on the same GPT answers.

Similarly, Grok-generated answers are the hardest column for every judge, while Gemini-generated answers are generally easier. That makes raw diagonal differences partly generator-difficulty effects. 

This changes the highest-priority revision: **the paper needs a paired, answer-level analysis, not merely confidence intervals around the current diagonal contrast.**

# Step-by-step revision plan

## Step 1 — Redefine the research question and estimand

Replace the current question:

> Does a judge perform differently on its own model’s outputs than on other generators’ outputs?

with the cleaner question:

> On the exact same candidate answer, does the matching judge behave differently from nonmatching judges, after accounting for judges’ general performance differences?

Use **“same-deployment pairing effect”** rather than “same-model family bias.” The experiment has one exact deployment from each provider and no same-provider/different-model condition, so it cannot separate exact-model, provider-family, and style-familiarity effects.

Also replace “factual error” where appropriate with:

* “source-relative contradiction,”
* “reference-grounding error,” or
* “target perturbation error.”

The original passage is the evaluation reference; the experiment does not independently establish that every original passage is objectively correct.

**Deliverable:** rewrite the research question, title/subtitle, and terminology before rerunning the analysis.

A safer subtitle would be:

> **A Paired Matrix Study of Source-Contradiction Detection**

## Step 2 — Make the 275 validated records the primary benchmark

The paper calls the dataset a “300-record balanced set,” but only 275 records pass all five gates. Twenty-five are retained despite failures including leakage, invalid perturbation type, global inconsistency, and lack of answer causality. 

Under the deadline, do not spend time regenerating and rejudging 25 replacements unless that is inexpensive. Instead:

1. Run every headline result on the **275 validated records only**.
2. Put the 25 failed records in a separate analysis named:

   * “failed-validation diagnostic set,” or
   * “imperfect-intervention stress test.”
3. Include a full-versus-validated sensitivity table in the appendix.
4. Change the abstract from “300 globally consistent perturbations” to:

   > “275 validated perturbations and 25 failed-validation diagnostic cases.”
5. Stop calling the set “balanced” unless you explicitly define what was balanced. Perturber counts are 83/92/125, and perturbation-type counts are highly uneven. “Frozen stratified question set” or “selected intervention set” would be safer.
6. Explain exactly how one perturbation was selected from the three provider-generated candidates and why the final provider counts differ.

Also audit the intervention unit. The relation-inversion example changes the verdict, win/loss outcome, and stock-price consequence. That may be necessary for consistency, but it is no longer literally one atomic value. Define:

* the **target proposition**, and
* the accompanying **consistency edits**.

That formulation will also make target matching and localization more defensible.

## Step 3 — Repair the mismatch between the judge task and the gold label

The judge is asked whether the answer contains **any factual error**, while the gold label indicates whether the answer expresses the **specific induced perturbation**. Those are different tasks.

Appendix Table 7 exposes the problem: the purported false-positive judge identifies a possible SEC-versus-FASB grounding problem. It may be detecting a genuine alternate error rather than hallucinating an error. The current gold cannot distinguish those possibilities. 

Create two separate endpoints.

### Primary endpoint: target-error detection

For every answer define:

```text
gold_target_present
```

This should be true whenever the answer asserts or entails the replacement proposition, including “both claims” cases. For conflict-aware outputs, specify explicitly whether the replacement is merely quoted as conflicting evidence or actually asserted.

For every judge verdict define:

```text
judge_target_detected
```

This is true only when the judge’s `wrong_claim`, explanation, and cited passage identify the induced target contradiction. A broad `contains_factual_error=true` is insufficient by itself.

Then evaluate target detection using:

* target precision,
* target recall,
* target F1,
* target localization.

A judge that finds a different real error should be recorded as `alternate_error_detected`, not automatically counted as a target false positive.

### Secondary endpoint: any-error detection

Evaluate this only on a human-annotated subset, because determining whether an answer contains some other factual or grounding error requires comprehensive inspection.

**Deliverables:**

* A documented mapping from answer text to `gold_target_present`.
* A documented mapping from judge rationale to `judge_target_detected`.
* Counts showing how `context_follow`, `both_claims`, and `conflict_awareness` map to gold.
* A table separating genuine false alarms from alternate-error detections.

## Step 4 — Replace the diagonal analysis with a paired item-level analysis

Each candidate answer was judged by all three judges. Use that pairing.

For gold-positive answers, fit a matched model such as:

```text
judge_target_detected
    ~ judge
    + same_deployment_pair
    + judge:same_deployment_pair
    + strata(answer_id)
```

Run the corresponding model on gold-negative answers to estimate target false-positive behavior.

A mixed-effects alternative is:

```text
judge_target_detected
    ~ judge
    + generator
    + same_deployment_pair
    + judge:same_deployment_pair
    + (1 | question_id)
    + (1 | answer_id)
```

The key requirement is that comparisons be made **within the same answer**, not across unrelated generator columns.

For uncertainty:

1. Resample by base `question_id`, retaining all three generator answers and all available judge verdicts.
2. Use approximately 10,000 cluster-bootstrap replicates.
3. Report 95% intervals for:

   * same-pair recall difference,
   * same-pair false-positive-rate difference,
   * each judge-specific interaction,
   * all nine matrix cells.
4. Apply a multiple-testing correction to the three judge-specific interactions, or mark them explicitly as exploratory.

Keep the 3×3 F1 matrix because it is useful descriptively, but do not use averaged F1 as the main inferential statistic. F1 is nonlinear and varies with each generator column’s positive prevalence and answer mixture.

### Decision rule for the rewrite

* If the global pairing interval includes zero, report **no robust global same-deployment effect**.
* If no provider interaction survives uncertainty correction, remove the GPT/Gemini/Grok signature claims.
* If one interaction survives, report only that interaction, with its interval and validated-only robustness check.
* Do not retain the current “opposing signatures cancel” narrative merely because the raw bars point in different directions.

A null or small controlled effect is still a worthwhile GroundLM result. The workshop explicitly welcomes negative results. ([GroundLM][1])

## Step 5 — Conduct a focused human audit

The current gold and generator behavior labels come from another LLM, and judge calls are single-shot—both already acknowledged in Limitations. 

A realistic deadline-compatible audit would cover:

1. **All 25 failed-validation perturbations.**
2. **75 validated perturbations**, stratified by perturbation type and selected perturber.
3. **90 candidate answers**:

   * 30 target-positive,
   * 30 target-negative,
   * 30 judge-disagreement or apparent-false-positive cases.
4. Preferably, every deduplicated candidate answer that was counted as a false positive; if there are too many, sample evenly by judge and generator.
5. Two annotators on at least 50 overlapping cases, followed by adjudication.

Annotation questions should be narrowly factual:

```text
Is the target replacement asserted?
Is the original proposition asserted?
Are both asserted?
Is the answer a refusal or conflict report?
Does it contain another contradiction with the source?
Did the judge identify the target error?
Did the judge identify a different valid error?
Is the cited passage the correct target passage?
```

Report raw agreement and Cohen’s κ or Krippendorff’s α. Even a modest human audit will materially improve reviewer confidence.

## Step 6 — Add the analyses that explain the matrix

Use existing data for these; they should not require new generation.

### A. Performance by generator behavior

Report judge target recall/FPR separately for:

* context-follow,
* both claims,
* conflict awareness,
* memory override,
* refusal/insufficient evidence,
* unrelated/failed.

The manuscript currently attributes Grok-column difficulty to refusals and hedging, but that remains an interpretation. Show it directly.

Also split `unrelated/failed` if possible. It currently covers 16–32% of outputs and likely combines several distinct situations. Generator behavior varies substantially across models, including Grok’s much higher refusal rate and GPT’s larger unrelated/failed category. 

### B. Remove or demote generator-side “self-affinity”

Section 5.2 compares following rates for perturbations created by the same versus other families. But Appendix Figure 11 shows strong perturber-specific type preferences: GPT contributes many causal changes, Grok more entity/numerical substitutions, and Gemini many entity substitutions and relation inversions. 

Therefore, Table 2 currently mixes perturber identity with perturbation type and difficulty. Either:

* remove this analysis from the main paper, or
* fit a controlled model including perturbation type, validation status, question, answer length, and target characteristics.

Do not say that Gemini generator behavior “foreshadows” Gemini judge self-skepticism without a supported controlled effect.

### C. Improve localization metrics

Current passage-localization rates are conditional on true-positive detections. Add:

* **joint localized recall**: percentage of all target-positive cases both detected and correctly localized;
* chance localization based on `modified_passages / all_passages`;
* semantic target-claim matching rather than exact replacement-token containment;
* localization results after removing answer-provided passage citations on a small subset.

Because generators were instructed to cite passage IDs, the judge may partly inherit localization information from the candidate answer.

### D. Add inexpensive baselines

Report:

* the existing deterministic target/replacement matcher;
* majority vote across the three judges;
* a leave-one-family-out or cross-judge ensemble;
* optionally, a standard NLI contradiction baseline.

These make the resource more useful and establish whether the expensive judge pipeline improves on simple alternatives.

## Step 7 — Rewrite the manuscript around the controlled result

### Abstract

Remove:

* the raw-data-audit implementation detail;
* “300 globally consistent perturbations”;
* unqualified GPT/Gemini/Grok signature claims.

Use a result sentence of this form:

> Across a fully crossed 3×3 matrix, raw diagonal differences are small and heterogeneous. After paired answer-level analysis, we find [no robust global same-deployment effect / a supported effect for X only], while generator behavior and answerability explain substantial variation in judge performance.

Use the actual result after reanalysis.

### Contributions

Reduce five contributions to three:

1. A controlled, blinded intervention protocol for evaluating source-contradiction judges.
2. A fully crossed and paired judge-by-generator benchmark with target-level localization.
3. Empirical evidence about pairing effects, generator behavior, and judge reliability after controlled analysis.

“Writing an audit script” and “providing schemas and examples” are good reproducibility practices, not standalone scientific contributions.

### Methods

Add one compact table with:

* exact provider and model/deployment ID;
* API version;
* access date;
* role: perturber, validator, labeler, generator, or judge;
* temperature, top-p, max tokens;
* retry policy and structured-output settings.

The current generic GPT/Grok/Gemini labels are not enough for model-specific claims, even though deployment IDs exist in the JSONL artifacts. 

Also explain:

* the three missing behavior labels;
* the 17 missing judge verdicts;
* how `unclear` maps to the boolean field;
* whether contradictory `verdict` and `contains_factual_error` values occurred;
* why confidence is collected.

Either analyze confidence calibration or remove confidence from the reported schema.

### Discussion and conclusion

Add a short explicit **Conclusion** before Limitations. The strongest takeaway should probably be:

> Full matrices are useful, but raw diagonal-versus-off-diagonal comparisons can themselves be misleading unless generator difficulty and answer-level pairing are controlled.

This is more defensible and more generally useful than three provider-specific personality descriptions.

### Limitations

Add the threats currently missing:

* broad-error prompt versus target-error gold;
* failed-validation records in the full set;
* confounding of perturber identity and perturbation type;
* absence of comprehensive human factuality annotation;
* citations inside candidate answers;
* inability to separate exact-model and provider-family effects.

## Step 8 — Update the closest related work

The most important missing citation is Chen et al. (2025), which directly studies self-preference in fact-centric RAG and reports no significant overarching self-preference across five models and three QA datasets. Your paper must explain how source intervention, answer-level localization, and the fully crossed judge matrix differ from that work. ([ACL Anthology][2])

Also add:

* **ContextualJudgeBench**, especially because it prioritizes refusal correctness and faithfulness—precisely the behavior affecting your Grok column. 
* **REFLECT**, a May 2026 meta-evaluation benchmark using controlled localized interventions and verifiable judge-failure labels. Its domain differs, but its methodological framing is very close. ([arXiv][3])
* **RAGferee** as recent work on RAG-specific contextual evaluators. ([ACL Anthology][4])

Update GaRAGe from the arXiv citation to the archival Findings of ACL 2025 publication. ([ACL Anthology][5])

A concise differentiation paragraph could say:

> Prior fact-centric RAG work examines self-preference through reranking and pairwise comprehension, while contextual-judge benchmarks evaluate refusal and faithfulness across curated response pairs. Our protocol instead intervenes on the retrieved source, generates natural responses from the altered source, and evaluates target-contradiction detection in a fully crossed, answer-paired judge matrix.

## Step 9 — Fix page-limit and presentation risks

The current paper effectively uses pages 1–8 for the main narrative, but places a separate Reproducibility Statement on page 9 before references. ACL rules provide unlimited post-conclusion space specifically for Limitations and optional Ethical Considerations, not an arbitrary reproducibility section. Move Reproducibility to an appendix after the references or fit it inside the eight content pages. Also add a clear Conclusion before Limitations. ([ACL Rolling Review][6])

Specific layout fixes:

* Correct Figure 4 appearing before Figure 3.
* Remove duplicate table/figure pairs:

  * Table 1 versus Figure 5,
  * Table 2 versus Figure 6,
  * Table 3 versus Figure 7,
  * Table 4 versus Figure 8,
  * Figure 9 versus Appendix Table 11.
* Use the recovered space for intervals, the validated-only matrix, and the human audit.
* Repair appendix floats: several headings are detached from their tables, while pages 13–15 contain excess whitespace.
* Enlarge the labels in Appendix Figure 11.
* Remove revision-history language such as “The prior draft…” and “For this revision…”.
* Refer to the uploaded anonymous supplement rather than an unspecified repository.
* Check supplementary filenames, metadata, commit history, and paths for author-identifying information.

# Six-day execution schedule

**June 23:** Freeze the estimand, create the 275-record primary set, define target-aware labels, and remove the 25 failed records from headline analyses.

**June 24:** Implement paired models and question-clustered bootstrap intervals. Produce validated-only matrix, target TPR/FPR, and same-pair effects.

**June 25:** Complete the focused human audit and reconcile alternate errors versus genuine false positives.

**June 26:** Run behavior-stratified analysis, localization improvements, and simple baselines. Decide the final headline based on the controlled results.

**June 27:** Rewrite the abstract, contributions, results, discussion, limitations, and related work. Add exact model and inference details.

**June 28:** Fix figures, floats, page limits, anonymity, and supplementary materials. Have someone not involved in the analysis read the PDF as a skeptical reviewer.

**June 29:** Final consistency check and submission buffer. The official direct-submission deadline is June 29 AoE. ([GroundLM][1])

# Minimum viable revision

For an archival submission, I would treat these five changes as non-negotiable:

1. Make the 275 validated records primary.
2. Replace broad-error scoring with target-aware scoring or manually adjudicate apparent false positives.
3. Replace row-wise diagonal deltas with answer-paired analysis and confidence intervals.
4. Rewrite the abstract and conclusions according to the controlled result.
5. Add the closest related work and eliminate the page-limit risk.

With those changes, the paper becomes a credible workshop accept: the protocol and resource are valuable even if the correct finding is that **same-deployment bias is small or not statistically distinguishable, while generator behavior strongly affects judge evaluation**. Without the first three changes, the central claim remains vulnerable enough that I would expect a borderline or weak-reject review.

[1]: https://groundlm.github.io/grouplm_emnlp2026/ "GroundLM 2026 | EMNLP 2026 Workshop"
[2]: https://aclanthology.org/2025.findings-acl.1369/ "LLMs are Biased Evaluators But Not Biased for Fact-Centric Retrieval Augmented Generation - ACL Anthology"
[3]: https://arxiv.org/html/2605.19196v1?utm_source=chatgpt.com "Time to Reflect : Can We Trust LLM Judges for Evidence- ..."
[4]: https://aclanthology.org/2025.emnlp-main.414/?utm_source=chatgpt.com "Building Contextual Reward Models for Retrieval ..."
[5]: https://aclanthology.org/2025.findings-acl.875/?utm_source=chatgpt.com "A Benchmark with Grounding Annotations for RAG ..."
[6]: https://aclrollingreview.org/cfp "CALL FOR PAPERS – ACL Rolling Review – A peer review platform for the Association for Computational Linguistics"
