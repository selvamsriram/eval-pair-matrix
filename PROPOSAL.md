# Do Models See Their Own RAG Mistakes?

## A Pairwise Study of Self-, Sibling-, and Cross-Family LLM Evaluators Under Controlled Long-Document Perturbations

### Short Title

Eval Pair Matrix for RAG

### Lead Research Question

Which responder-evaluator pairings are actually reliable for evaluating retrieval-augmented generation, and do models exhibit unique blind spots when asked to judge answers produced by themselves or by closely related models?

### One-Sentence Thesis

LLM-based RAG evaluation should not treat the evaluator model as an interchangeable oracle: the identity and family relationship between the answer generator and the judge may systematically affect defect detection, especially for subtle, source-grounded errors in long-context settings.

---

## 1. Abstract

RAG systems are increasingly evaluated by other language models, but the choice of evaluator is often made informally. A common practice is to use the same frontier model, a smaller sibling model, or a nearby model family as the judge of RAG outputs. This creates a central measurement risk: if generator and evaluator share model lineage, training preferences, response style, or evidence-selection habits, the evaluator may be unusually poor at recognizing mistakes that the generator is inclined to make.

This project proposes a controlled pairwise evaluation matrix for long-document RAG. Multiple responder models generate answers to LongSeal-style search-augmented QA instances under carefully controlled perturbations. Multiple evaluator models then audit those answers without being given the final gold answer, receiving only the question, retrieval context, and candidate response. The core experimental object is a responder-by-evaluator matrix that compares self-pairing, sibling-pairing, and cross-family evaluation. The main scientific outcome is not merely whether self-evaluation is biased, but what makes self-pairing failures distinctive: shared style familiarity, shared evidence attention, shared reasoning shortcuts, or common inability to detect specific defect types.

The study is designed to be feasible for a solo researcher with AI-agent assistance. It uses a high-quality long-document benchmark, a compact perturbation ledger, structured judge outputs, paired statistical tests, mixed-effects models, targeted human adjudication, and a staged execution plan that can yield a credible pilot in 1 to 2 weeks and a stronger paper-quality result in 3 to 4 weeks.

---

## 2. Motivation

LLM-as-a-judge pipelines have become a practical default for evaluating open-ended model outputs. They are scalable, cheap relative to expert annotation, and can produce explanations, rubric scores, and structured error labels. However, prior work has shown that model judges are not neutral instruments. They can show position bias, verbosity bias, style preference, self-preference, and inconsistent reasoning. This becomes especially concerning in RAG, where the evaluator must verify factual support against retrieved evidence rather than merely judge conversational helpfulness.

RAG evaluation has an additional complication: an answer can look excellent while being wrong in exactly the kind of way the generating model prefers. A model may over-trust a misleading document, ignore a buried contradicting span, overgeneralize a qualifier, or combine two true facts into a false synthesis. If the same model, or a close sibling, is then asked to judge the answer, it may reproduce the same evidence-selection or reasoning pattern and fail to catch the defect.

This project targets that gap. It asks whether evaluator choice should be treated as an experimental variable in RAG evaluation, not merely an implementation detail.

---

## 3. Background and Related Work

### 3.1 LLM-as-a-Judge

Zheng et al. introduced MT-Bench and Chatbot Arena and studied the use of strong LLMs as judges, while also noting limitations such as position, verbosity, self-enhancement biases, and limited reasoning ability: [Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena](https://arxiv.org/abs/2306.05685).

Wang et al. showed that LLM evaluators can be highly sensitive to answer ordering and proposed calibration strategies such as balanced position calibration and human-in-the-loop calibration: [Large Language Models are not Fair Evaluators](https://aclanthology.org/2024.acl-long.511/).

Liu et al. proposed G-Eval, using form-filling and chain-of-thought-style prompting for NLG evaluation: [G-Eval](https://arxiv.org/abs/2303.16634). This helped establish the practical pattern of using strong LLMs as structured evaluators.

### 3.2 Self-Preference and Familiarity Bias

Wataoka et al. studied self-preference bias in LLM-as-a-judge and argued that models may prefer outputs that are more familiar or lower-perplexity under their own distribution: [Self-Preference Bias in LLM-as-a-Judge](https://arxiv.org/abs/2410.21819).

Chen et al. distinguished harmful self-preference from legitimate self-preference using verifiable benchmarks. Their key insight is directly relevant here: stronger models often prefer themselves for legitimate reasons, but harmful self-preference persists when they are wrong as generators: [Do LLM Evaluators Prefer Themselves for a Reason?](https://arxiv.org/abs/2504.03846).

This project extends that line of work into long-context RAG, where correctness depends on source-grounded verification rather than preference among answers.

### 3.3 Factuality and Claim-Level Verification

FActScore decomposes long-form generations into atomic facts and verifies each against a source of truth: [FActScore](https://arxiv.org/abs/2305.14251). This motivates claim-level scoring rather than relying only on global quality scores.

The proposed study adopts the same broad lesson: evaluator performance should be measured at the level of individual defect opportunities, evidence spans, and localized claims.

### 3.4 LongSeal as the Testbed

SealQA is a benchmark for search-augmented language models under conflicting, noisy, or unhelpful search results. Its LongSeal split is designed for long-context, multi-document reasoning in a needle-in-a-haystack setting: one helpful document is buried among hard negatives. The dataset card reports how to load the `longseal` split via Hugging Face: [vtllms/sealqa](https://huggingface.co/datasets/vtllms/sealqa). The SealQA paper describes LongSeal as 254 questions paired with retrieved documents, where only one document contains or implies the correct answer: [SealQA paper](https://arxiv.org/abs/2506.01062).

LongSeal is a strong fit because the proposed study needs difficult, realistic RAG contexts where models can plausibly attend to the wrong evidence.

---

## 4. Core Scientific Contribution

The project contributes a controlled methodology for measuring responder-evaluator compatibility in RAG:

1. A responder-by-evaluator pairing matrix for self, sibling, and cross-family judgment.
2. A perturbation-ledger method for creating known, subtle RAG defects.
3. Defect-level metrics that measure what each evaluator actually catches.
4. A taxonomy of self-pairing blind spots.
5. Practical recommendations for choosing RAG evaluators and evaluator ensembles.

The study is designed so that a null result is still valuable. If self-pairing is not worse under rigorous source-grounded evaluation, that would challenge a common assumption and support the use of same-model evaluators under constrained conditions. If self-pairing is worse only for certain defect types, the paper can give precise guidance rather than a vague warning.

---

## 5. Research Questions

### RQ1: Pairing Effect

Are models less likely to detect defects in RAG answers generated by themselves than defects generated by other model families?

### RQ2: Sibling Effect

Do models from the same provider family or model lineage show shared evaluator blind spots, even when generator and judge are not exactly the same model?

Examples:

- GPT-5.4 responder judged by GPT-5.4 mini.
- Sonnet 4.6 responder judged by Haiku or another Claude-family model.
- Gemini Pro responder judged by Gemini Flash.

### RQ3: Defect Specificity

Which defect types are disproportionately missed in self or sibling pairings?

Candidate defect families include entity swaps, temporal errors, scope errors, causal overreach, unsupported synthesis, citation mismatch, and omission of decisive qualifiers.

### RQ4: Mechanism

What is unique about self-pairing failures?

Candidate mechanisms:

- Style familiarity: the evaluator is more forgiving of its own answer style.
- Shared evidence attention: responder and evaluator rely on the same misleading span.
- Shared reasoning shortcut: both models make the same inference leap.
- Confidence contagion: fluent, well-structured answers from the same family suppress skepticism.
- Rubric interpretation similarity: related models operationalize correctness in similar ways.

### RQ5: Ensemble Reliability

Do cross-family evaluator ensembles detect more defects than any single evaluator, and how many evaluators are needed before marginal gains flatten?

### RQ6: Practical Recommendation

For a real RAG pipeline, when is self-evaluation acceptable, when is a sibling judge risky, and when is cross-family or human-in-the-loop evaluation necessary?

---

## 6. Hypotheses

### H1: Self-Pairing Blind Spot

For answer-level defects that are objectively present relative to the source context, self-pairings will have lower defect recall than cross-family pairings.

### H2: Sibling-Pairing Blind Spot

Same-family evaluators will show intermediate performance: better than exact self-pairing but worse than cross-family evaluation for at least some defect types.

### H3: Defect-Type Interaction

The self-pairing penalty will be largest for defects that arise from reasoning style rather than surface fact lookup:

- unsupported synthesis
- scope and quantifier drift
- causal overreach
- omission of decisive qualifiers
- multi-hop composition errors

The penalty may be smaller for blatant entity, date, or numeric substitutions.

### H4: Style-Normalization Mediation

If self-pairing failure is partly caused by style familiarity, then rewriting candidate answers into a neutral canonical style before evaluation should reduce the self-pairing penalty.

### H5: Evidence-Overlap Mediation

If self-pairing failure is partly caused by shared evidence attention, then missed defects will correlate with overlap between the responder's cited or implied evidence and the evaluator's cited evidence.

### H6: Cross-Family Complementarity

Evaluator ensembles composed of different model families will achieve higher defect recall and better calibration than same-family or same-model repeated judging.

---

## 7. Operational Definitions

### Responder

The model that answers a RAG question from retrieved documents.

### Evaluator

The model that audits a candidate RAG answer for source-grounded correctness.

### Self-Pairing

The responder and evaluator are the exact same model snapshot or deployment ID.

Example: GPT-5.4 answers, GPT-5.4 judges.

### Sibling-Pairing

The responder and evaluator are different models from the same provider family or likely lineage.

Example: Sonnet answers, Haiku judges.

### Cross-Family Pairing

The responder and evaluator come from different provider/model families.

Example: Sonnet answers, Gemini judges.

### Defect Opportunity

A known injected error or source-induced trap that a correct evaluator could detect from the evaluation packet.

### Defect Recall

The fraction of known defect opportunities correctly identified by the evaluator.

### False Positive

A reported defect that is not supported by the perturbation ledger, source context, or human adjudication.

### Source-Grounded Correctness

Whether the candidate answer is justified by the provided trustworthy source context, independent of whether the answer sounds plausible.

---

## 8. Model Matrix

The exact model names below should be treated as planned labels. The experiment must freeze concrete model IDs, provider API versions, dates, decoding parameters, and system prompts before running.

### Primary 4x4 Matrix

| Responder / Evaluator | GPT-5.4 | Sonnet 4.6 | Gemini 3.1 Pro | Kimi K2.6 |
| --- | --- | --- | --- | --- |
| GPT-5.4 | self | cross | cross | cross |
| Sonnet 4.6 | cross | self | cross | cross |
| Gemini 3.1 Pro | cross | cross | self | cross |
| Kimi K2.6 | cross | cross | cross | self |

### Extended Matrix

Add sibling evaluators where feasible:

| Family | Responder | Sibling Evaluator |
| --- | --- | --- |
| OpenAI | GPT-5.4 | GPT-5.4 mini |
| Anthropic | Sonnet 4.6 | Haiku-class model |
| Google | Gemini 3.1 Pro | Gemini Flash-class model |
| xAI | Grok current flagship | smaller/current sibling if available |
| Meta | Llama flagship/open-weight | Llama smaller/open-weight sibling |
| Moonshot | Kimi K2.6 | smaller/current Kimi sibling if available |

### Practical Recommendation

For a short solo project, run the primary 4x4 matrix first. Then add sibling pairings only for the families where API access, cost, and model stability are manageable.

---

## 9. Dataset

### Primary Dataset

Use LongSeal from SealQA:

- Compact enough for a solo project.
- Long-context and multi-document.
- Designed around noisy, misleading, or irrelevant retrieved content.
- Contains hard negatives and one helpful document per question.
- Suitable for source-grounded auditing without giving evaluators the final gold answer.

### Dataset Size Strategy

Use staged sampling:

| Stage | Questions | Perturbations Per Question | Approx. Variants | Purpose |
| --- | ---: | ---: | ---: | --- |
| Smoke test | 10 | 1 | 10 | Validate pipeline and schemas |
| Pilot | 40 | 2 | 80 | Estimate effect sizes and cost |
| Main short-run | 80 to 120 | 2 | 160 to 240 | Publishable workshop-scale result |
| Full LongSeal | 254 | 1 to 3 | 254 to 762 | Stronger archival paper result |

The pilot should be considered successful if it produces stable parsing, nontrivial defect propagation, and visible variation across pairings.

---

## 10. Experimental Design Overview

The design uses two complementary arms.

### Arm A: Source-Perturbation Arm

This arm preserves the user's core idea.

1. Start with a LongSeal question and its retrieved document set.
2. Identify the helpful document and answer-bearing span.
3. Introduce a subtle mutation into the helpful document.
4. Record the mutation in a perturbation ledger.
5. Ask responder models to answer the question using the perturbed retrieval context.
6. Determine whether each candidate answer propagated the mutation.
7. Ask evaluator models to audit the candidate answer without the final gold answer.

This arm tests whether evaluators can catch RAG mistakes induced by corrupted or misleading evidence.

### Arm B: Answer-Perturbation Control Arm

This arm is necessary for clean measurement.

1. Keep the retrieval context unmodified.
2. Generate or use a correct answer.
3. Inject one controlled defect directly into the candidate answer.
4. Ask evaluator models to detect the defect using the original source context.

This arm tests evaluator sensitivity without confounding the result with whether the responder propagated a source mutation.

### Why Both Arms Are Needed

If the source document itself is corrupted and the evaluator sees only the same corrupted document, the evaluator may have no legitimate way to know the source is wrong. That would measure external fact-checking or prior knowledge, not RAG faithfulness. Arm A is scientifically interesting but must be handled carefully. Arm B gives a clean source-grounded measurement anchor.

The strongest paper uses both:

- Arm A captures realistic RAG failure formation.
- Arm B captures controlled evaluator detection.

---

## 11. Evaluation Packet Conditions

Each evaluator receives one of the following packets, depending on experimental condition.

### Condition 1: Standard Source-Grounded Audit

The evaluator receives:

- User question.
- Retrieved context.
- Candidate answer.
- Rubric.

The evaluator does not receive:

- Final gold answer.
- Perturbation record.
- Responder identity.
- Whether the answer is intentionally corrupted.

This is the main condition.

### Condition 2: Original-Context Audit for Source-Perturbation Arm

The responder receives perturbed context, but the evaluator receives original unperturbed context. This allows the evaluator to catch propagated source-induced errors without being told the gold answer.

This condition answers:

Can evaluators detect that the answer conflicts with the reliable original evidence?

### Condition 3: Same-Context Audit for Source-Perturbation Arm

The evaluator receives the same perturbed context as the responder.

This condition answers:

Does the evaluator merely check faithfulness to the supplied context, or can it notice internal contradictions, suspicious evidence, or conflicts with other retrieved documents?

This should be treated as exploratory, because detecting a corrupted but internally consistent source may require outside knowledge.

### Condition 4: Style-Normalized Audit

Before evaluation, candidate answers are converted into a neutral, canonical style:

- same length band
- same citation format
- same confidence style
- no provider-specific phrasing
- no markdown flourish

This condition tests whether self-pairing failures are mediated by answer style.

---

## 12. Perturbation Taxonomy

Each perturbation should be small, plausible, and localized. The goal is not to create obvious nonsense. The goal is to create realistic RAG failure opportunities.

### 12.1 Entity Swap

Replace an answer-bearing entity with a plausible confounder.

Example pattern:

- Original: Company A first reached a threshold.
- Mutated: Company B first reached the threshold.

### 12.2 Temporal Shift

Change a date, ordering, recency condition, or temporal qualifier.

Example pattern:

- "most recently"
- "first"
- "before"
- "after"
- "as of 2025"

### 12.3 Quantity or Numeric Drift

Change a number, rank, count, percentage, score, or threshold.

### 12.4 Scope or Quantifier Drift

Change the scope of a claim.

Examples:

- "some" to "all"
- "in one trial" to "generally"
- "among public companies" to "among all companies"
- "at least three" to "exactly three"

### 12.5 Negation or Polarity Flip

Invert a key relation while preserving fluent prose.

### 12.6 Causal Overreach

Change correlational, associative, or chronological language into causal language.

### 12.7 Attribution Error

Assign an action, quote, result, or property to the wrong person, organization, team, paper, or jurisdiction.

### 12.8 Evidence-Citation Mismatch

Make an answer cite a source span that appears related but does not support the claim.

### 12.9 Omitted Qualifier

Remove a critical limitation or exception that changes answer correctness.

### 12.10 Multi-Hop Composition Error

Make two individually true facts combine into a false conclusion.

### 12.11 Distractor Adoption

Modify a hard negative so it becomes more tempting, then measure whether responders and evaluators follow it.

### 12.12 False-Premise Preservation

Preserve a false assumption in the question or source rather than correcting it.

---

## 13. Perturbation Ledger

Every mutation must be recorded in a machine-readable ledger before model generation.

Suggested schema:

```json
{
  "item_id": "longseal_0001",
  "variant_id": "longseal_0001_temporal_shift_01",
  "question": "...",
  "original_gold_answer": "...",
  "helpful_doc_id": "doc_17",
  "hard_negative_doc_ids": ["doc_03", "doc_11"],
  "perturbation_type": "temporal_shift",
  "severity": "major",
  "difficulty": "subtle",
  "original_span": "...",
  "mutated_span": "...",
  "expected_false_claim": "...",
  "minimal_correct_detection": "Evaluator should identify that the candidate answer uses the wrong date and cite the original source span.",
  "valid_detection_aliases": [
    "wrong date",
    "recency error",
    "temporal contradiction"
  ],
  "source_condition": "answer_bearing_gold_doc_mutation",
  "human_validated": true,
  "notes": "Mutation preserves grammar and topical plausibility."
}
```

The ledger is the scientific backbone of the study. It allows evaluator outputs to be scored against known hidden defects rather than vague subjective preference.

---

## 14. Response Generation Protocol

### Responder Prompt

The responder should receive:

- System instruction: answer only from provided context.
- User question.
- Retrieved documents with stable document IDs.
- Requirement to cite document IDs and short evidence snippets.
- Instruction to abstain if context is insufficient.

### Generation Parameters

Recommended defaults:

- Temperature: 0 or 0.2.
- Top-p: provider default or 1.0.
- Max tokens: enough for a complete answer, typically 500 to 1000.
- One generation per item for main study.
- Three generations per item for a smaller robustness subset.

### Why Low Temperature

The purpose is not to sample creative variation. The purpose is to compare systematic responder-evaluator compatibility. Low temperature reduces noise and cost.

### Responder Output Schema

```json
{
  "answer": "...",
  "citations": [
    {
      "doc_id": "doc_17",
      "quoted_evidence": "...",
      "supports_claim": "..."
    }
  ],
  "confidence": "high|medium|low",
  "abstained": false
}
```

If a provider cannot reliably produce strict JSON, preserve raw text and parse it with a separate parser agent, but do not silently discard malformed responses.

---

## 15. Evaluator Protocol

### Core Evaluator Instruction

The evaluator is an auditor, not a preference judge. It must verify whether the candidate answer is supported by the provided documents.

The evaluator should not receive:

- gold answer
- mutation ledger
- responder identity
- pair category
- other evaluators' judgments

### Evaluator Output Schema

```json
{
  "verdict": "correct|partially_incorrect|incorrect|insufficient_context|uncertain",
  "overall_confidence": 0.0,
  "detected_defects": [
    {
      "claim": "...",
      "defect_type": "entity_swap|temporal_shift|quantity_error|scope_error|causal_overreach|unsupported_claim|contradicted_claim|citation_mismatch|omitted_qualifier|multi_hop_error|other",
      "severity": "minor|major|critical",
      "explanation": "...",
      "evidence": [
        {
          "doc_id": "doc_17",
          "span": "...",
          "relationship": "contradicts|fails_to_support|qualifies|supports"
        }
      ],
      "confidence": 0.0
    }
  ],
  "unsupported_claims": ["..."],
  "missing_qualifications": ["..."],
  "recommended_corrected_answer": "..."
}
```

### Important Prompting Constraint

Do not ask evaluators to "score helpfulness." Helpfulness is too broad and invites preference bias. Ask for source-grounded defect detection.

### Rationale Handling

Ask for concise evidence-backed rationales, not long hidden reasoning traces. The output should be auditable through cited spans.

---

## 16. Scoring

### 16.1 Primary Metric: Defect-Level Recall

For each known defect opportunity, score whether the evaluator identified it.

An evaluator gets credit if it:

- identifies the affected claim,
- describes the correct defect family or an accepted alias,
- cites or references evidence sufficient to justify the detection.

Formula:

```text
defect_recall = detected_known_defects / total_known_defect_opportunities
```

### 16.2 Secondary Metrics

#### Verdict Accuracy

Whether the evaluator's global verdict matches the adjudicated answer status.

#### False Positive Rate

How often the evaluator reports defects that are not actually present.

#### Localization Accuracy

Whether the evaluator cites the correct document and span.

#### Severity Calibration

Whether the evaluator assigns appropriate severity to detected defects.

#### Confidence Calibration

Compare confidence scores with correctness using Brier score or expected calibration error.

#### Evidence Precision

Fraction of cited evidence spans that actually support the evaluator's critique.

#### Abstention Quality

Whether "insufficient context" or "uncertain" is used appropriately.

#### Repair Accuracy

Whether the evaluator's corrected answer is supported by the source context.

### 16.3 Pairing-Level Metrics

For each responder-evaluator pair:

- mean defect recall
- false positive rate
- verdict accuracy
- localization accuracy
- calibration error
- average severity-weighted recall

### 16.4 Severity-Weighted Recall

Major and critical defects should matter more than minor defects.

Example:

```text
weighted_recall =
  sum(weight(defect_i) * detected_i) / sum(weight(defect_i))
```

Suggested weights:

- minor: 1
- major: 2
- critical: 3

---

## 17. Main Statistical Analysis

### Unit of Analysis

The primary unit is the defect opportunity:

```text
question x perturbation x responder x evaluator
```

### Main Model

Use a mixed-effects logistic regression:

```text
DetectedDefect ~ PairingCategory
               + DefectType
               + ResponderModel
               + EvaluatorModel
               + AnswerLength
               + HelpfulDocPosition
               + CitationPresent
               + (1 | QuestionID)
               + (1 | PerturbationID)
```

Where `PairingCategory` is:

- self
- sibling
- cross-family

Primary contrast:

```text
self recall < cross-family recall
```

Secondary contrast:

```text
sibling recall < cross-family recall
```

### Pairwise Tests

Because every candidate answer can be judged by every evaluator, use paired comparisons where possible.

Recommended tests:

- cluster bootstrap confidence intervals over questions
- McNemar-style paired tests for binary detection on matched cases
- Bayesian hierarchical logistic model as an optional robustness check
- Benjamini-Hochberg correction for multiple defect-type comparisons

### Effect Sizes

Report:

- absolute recall difference in percentage points
- odds ratio for detection
- false-positive difference
- severity-weighted recall difference
- calibration difference

Avoid relying only on p-values.

### Minimum Meaningful Effect

Before running the main study, define a practically meaningful effect.

Suggested threshold:

- 5 percentage points: operationally noticeable
- 10 percentage points: practically important
- 15+ percentage points: strong self-pairing blind spot

---

## 18. Mechanism Analyses

### 18.1 Style-Normalization Test

Compare raw answers with style-normalized answers.

Interpretation:

- If self-pairing penalty shrinks substantially, style familiarity is likely contributing.
- If self-pairing penalty remains, the blind spot is likely not just style.

### 18.2 Evidence-Overlap Test

Log responder citations and evaluator citations.

Compute:

```text
doc_overlap = Jaccard(responder_cited_doc_ids, evaluator_cited_doc_ids)
span_overlap = approximate lexical or embedding overlap between cited spans
```

Interpretation:

- High overlap on missed defects suggests shared evidence attention.
- Low overlap with missed defects suggests other mechanisms, such as evaluator leniency or rubric failure.

### 18.3 Defect-Type Fingerprints

For each evaluator, produce a vector of recall by defect type.

Then compare:

- self vs cross differences
- sibling-family clustering
- evaluator-specific weaknesses

This can reveal whether model families have distinct "error vision" profiles.

### 18.4 Fluency and Confidence Masking

Annotate or automatically measure:

- answer length
- citation count
- hedging frequency
- confidence language
- formatting polish
- readability

Test whether these surface features predict missed defects, especially in self-pairings.

### 18.5 Author-Style Probe

Optional but interesting:

Ask a separate classifier model to guess which family generated each answer from style alone. If self-pairing failures are concentrated in answers with highly identifiable family style, this supports the style-familiarity hypothesis.

---

## 19. Human Adjudication

Human review is needed, but it can be targeted.

### Human Review Set

Review:

- 100 percent of perturbation ledger entries in the pilot.
- 20 to 30 percent of ledger entries in the main run.
- all high-impact disagreements where evaluators diverge.
- all cases used as qualitative examples in the paper.

### Human Tasks

The human adjudicator verifies:

- mutation is valid and subtle,
- mutation does not accidentally introduce multiple defects,
- candidate answer actually contains or avoids the induced defect,
- evaluator detection scoring is fair,
- evidence spans support the adjudication.

### Adjudication Interface

Keep it lightweight:

- JSONL records.
- A local HTML review page or spreadsheet.
- Fields for `valid_mutation`, `answer_propagated_defect`, `evaluator_detected_defect`, and `notes`.

### Inter-Annotator Agreement

If possible, use AI agents for first-pass annotation and the solo researcher as final arbiter. If a second human is available for 50 to 100 cases, report agreement. If not, report this as a limitation and emphasize deterministic ledger-based scoring.

---

## 20. Experimental Controls

### 20.1 Blinding

Evaluator prompts must not reveal:

- responder model,
- provider,
- whether this is self or cross,
- perturbation type,
- whether the item is corrupted.

### 20.2 Prompt Invariance

Use the same evaluator prompt for every model except provider-specific formatting constraints.

### 20.3 Randomization

Randomize:

- item order,
- document order where appropriate,
- answer presentation order in any pairwise sub-experiment,
- assignment of perturbation types to questions.

Preserve random seeds.

### 20.4 Context Length Control

Track:

- total tokens,
- helpful document position,
- answer-bearing span position,
- number of documents,
- number of hard negatives.

Long-context location can affect performance, so it should be a covariate.

### 20.5 Answer Length Control

Longer answers contain more claims and may attract more criticism. Include answer length and number of atomic claims as covariates.

### 20.6 Model Capability Control

Some evaluators may simply be stronger. Report absolute evaluator performance and pairing-relative performance. A self-pairing penalty is most convincing when the same evaluator performs better on cross-family answers than on its own family's answers under matched conditions.

### 20.7 Provider Drift

Use exact model snapshots where possible. Record:

- provider,
- model ID,
- API version,
- run date,
- decoding parameters.

If exact snapshots are unavailable, run all conditions in a compact time window and report that limitation.

---

## 21. Minimal Achievable Study

This is the version a solo researcher can complete quickly.

### Scope

- 40 LongSeal questions.
- 2 perturbations per question.
- 4 responder models.
- 4 evaluator models.
- Main condition plus style-normalized ablation.
- Human validation of all 80 perturbation records and a sampled set of evaluator outputs.

### Approximate Workload

```text
80 variants x 4 responders = 320 candidate answers
320 answers x 4 evaluators = 1,280 evaluator judgments
Optional style-normalized audit: +1,280 judgments
Total: 1,280 to 2,560 judgments
```

This is tractable with automated runners and structured outputs.

### Success Criteria

The pilot is successful if:

- at least 70 percent of perturbations are judged valid by human review,
- at least 40 percent of source perturbations are propagated by at least one responder,
- evaluator JSON parse success exceeds 95 percent after repair,
- defect recall varies meaningfully across pairings,
- scoring pipeline produces stable heatmaps and confidence intervals.

---

## 22. Strong Short-Paper Study

This is the recommended target for a top-tier but short-timeframe result.

### Scope

- 80 to 120 LongSeal questions.
- 2 perturbations per question.
- 4 to 5 responder models.
- 4 to 5 evaluator models.
- At least one sibling evaluator per major family if feasible.
- Both source-perturbation and answer-perturbation arms.
- Style-normalized ablation on a representative subset.
- Human adjudication on 20 to 30 percent plus all featured examples.

### Approximate Workload

For 100 questions, 2 variants, 5 responders, 5 evaluators:

```text
200 variants x 5 responders = 1,000 candidate answers
1,000 answers x 5 evaluators = 5,000 evaluator judgments
Style-normalized subset, 25 percent: +1,250 judgments
Total: about 6,250 judgments
```

This is feasible if API calls are batched and all outputs are schema-constrained.

---

## 23. AI-Agent Workflow for a Solo Researcher

### Agent 1: Dataset Loader

Responsibilities:

- download LongSeal,
- normalize records,
- assign stable IDs,
- export JSONL packets.

### Agent 2: Evidence Span Finder

Responsibilities:

- identify the helpful document,
- locate answer-bearing spans,
- propose candidate perturbation sites.

### Agent 3: Perturbation Generator

Responsibilities:

- create subtle mutations,
- classify perturbation type,
- fill perturbation ledger fields.

### Agent 4: Mutation Validator

Responsibilities:

- reject mutations that are too obvious, too ambiguous, or multi-defect,
- verify grammar and plausibility,
- check that the mutated span changes the likely answer.

### Agent 5: Responder Runner

Responsibilities:

- call responder APIs,
- enforce generation prompt,
- store raw and parsed outputs,
- retry malformed outputs.

### Agent 6: Answer Defect Labeler

Responsibilities:

- compare candidate answers to perturbation ledger,
- determine whether known defects were propagated,
- decompose answer into atomic claims where needed.

### Agent 7: Evaluator Runner

Responsibilities:

- call evaluator APIs,
- hide responder identity,
- enforce structured outputs,
- store raw and parsed outputs.

### Agent 8: Scoring Agent

Responsibilities:

- match evaluator detections to ledger entries,
- compute recall, false positives, localization, calibration,
- flag uncertain cases for human review.

### Agent 9: Analysis and Figure Agent

Responsibilities:

- build heatmaps,
- run statistical models,
- generate paper-ready tables,
- summarize qualitative examples.

### Solo Researcher Role

The human researcher should own:

- final perturbation approval,
- final scoring rule decisions,
- interpretation of ambiguous cases,
- paper narrative,
- claims about mechanisms.

AI agents accelerate execution, but the scientific judgment must remain human-led.

---

## 24. Implementation Artifacts

Recommended repository structure:

```text
eval-pair-matrix/
  README.md
  PROPOSAL.md
  configs/
    models.yaml
    prompts.yaml
    experiment.yaml
  data/
    raw/
    processed/
    perturbations/
    generations/
    evaluations/
    adjudication/
  scripts/
    load_longseal.py
    create_perturbations.py
    run_responders.py
    run_evaluators.py
    score_evaluations.py
    analyze_results.py
  notebooks/
    01_pilot_analysis.ipynb
    02_main_results.ipynb
  reports/
    figures/
    tables/
    paper_draft.md
```

### Core Data Files

```text
data/processed/items.jsonl
data/perturbations/ledger.jsonl
data/generations/responses.jsonl
data/evaluations/judgments.jsonl
data/adjudication/human_review.jsonl
reports/tables/pairing_matrix.csv
reports/figures/defect_recall_heatmap.png
```

---

## 25. Suggested Prompt Templates

### 25.1 Responder Prompt

```text
System:
You answer questions using only the provided retrieved documents. If the documents do not contain enough information, say that the answer is not supported. Do not use outside knowledge.

User:
Question:
{question}

Retrieved documents:
{documents_with_ids}

Write a concise answer. Cite the document IDs and short evidence snippets that support your answer. Return JSON with:
- answer
- citations
- confidence: high, medium, or low
- abstained: true or false
```

### 25.2 Evaluator Prompt

```text
System:
You are auditing a retrieval-augmented answer for source-grounded correctness. Your job is to identify claims in the candidate answer that are unsupported, contradicted, overgeneralized, missing critical qualifications, or incorrectly cited by the provided documents. Do not judge writing style. Do not assume the answer is wrong. Do not use outside knowledge.

User:
Question:
{question}

Retrieved documents:
{documents_with_ids}

Candidate answer:
{candidate_answer}

Audit the candidate answer against the documents. You are not given a gold answer. Return JSON with:
- verdict: correct, partially_incorrect, incorrect, insufficient_context, or uncertain
- overall_confidence: number from 0 to 1
- detected_defects: list of defect objects
- unsupported_claims
- missing_qualifications
- recommended_corrected_answer
```

### 25.3 Style-Normalization Prompt

```text
System:
Rewrite the candidate answer into a neutral style while preserving every factual claim, citation reference, uncertainty level, and omission. Do not correct the answer. Do not add or remove factual content.

User:
Candidate answer:
{candidate_answer}

Return only the rewritten answer.
```

---

## 26. Expected Results

### Possible Finding 1: Self-Pairing Deficit

Self-pairing has lower defect recall than cross-family pairing, especially for reasoning-heavy defects.

Interpretation:

Same-model evaluation is risky for RAG auditing because generation and judgment share blind spots.

### Possible Finding 2: Sibling-Pairing Deficit

Sibling models show a smaller but still measurable deficit.

Interpretation:

Provider-family diversity matters. Using a cheaper sibling as judge may not provide independent scrutiny.

### Possible Finding 3: Style-Normalization Reduces the Effect

The self-pairing penalty shrinks after canonical rewriting.

Interpretation:

Part of the effect is caused by style familiarity or distributional comfort.

### Possible Finding 4: Style-Normalization Does Not Reduce the Effect

The self-pairing penalty remains after rewriting.

Interpretation:

The issue is more likely shared reasoning or shared evidence attention.

### Possible Finding 5: Cross-Family Ensembles Win

Two or three diverse evaluators outperform one strong evaluator, especially on severity-weighted recall.

Interpretation:

Evaluator diversity should be a default recommendation for high-stakes RAG evaluation.

### Possible Finding 6: Null Result

No significant self or sibling penalty appears after strict source-grounded prompting.

Interpretation:

Self-evaluation may be acceptable for constrained factual auditing if the prompt, schema, and evidence requirements are strong. This would still be a valuable result.

---

## 27. Figures and Tables

### Figure 1: Responder-Evaluator Matrix

Heatmap of defect recall for every responder-evaluator pair.

### Figure 2: Self vs Sibling vs Cross

Bar plot with cluster bootstrap confidence intervals.

### Figure 3: Defect-Type Breakdown

Recall by perturbation type and pairing category.

### Figure 4: Style-Normalization Ablation

Raw answer recall vs normalized answer recall.

### Figure 5: Evidence Overlap

Relationship between citation overlap and missed defects.

### Figure 6: Ensemble Curve

Defect recall as a function of number and diversity of evaluator models.

### Table 1: Model Roster

Exact model IDs, providers, run dates, and decoding parameters.

### Table 2: Perturbation Taxonomy

Counts and examples by defect type.

### Table 3: Statistical Contrasts

Self vs cross, sibling vs cross, with effect sizes and confidence intervals.

### Table 4: Qualitative Failure Modes

Representative cases with anonymized model labels.

---

## 28. Threats to Validity

### Artificial Perturbations

Injected defects may not perfectly match naturally occurring RAG failures.

Mitigation:

- use subtle, realistic mutation types,
- include source-induced and answer-induced arms,
- include qualitative analysis of naturally generated mistakes.

### Dataset Contamination

Models may have seen public benchmark questions.

Mitigation:

- perturb source spans,
- avoid giving gold answers to evaluators,
- analyze whether models answer without support,
- treat contamination as a limitation.

### Source-Perturbation Ambiguity

If the evaluator sees only corrupted context, detecting the source defect may be impossible without external knowledge.

Mitigation:

- separate original-context and same-context audit conditions,
- define the main metric on defect opportunities that are detectable from the evaluation packet.

### Model Drift

Provider models may change.

Mitigation:

- freeze exact model IDs where possible,
- record run dates,
- run all matrix conditions in a narrow time window,
- release raw outputs.

### Prompt Sensitivity

Evaluator behavior may depend on prompt wording.

Mitigation:

- use one prompt template across models,
- run a prompt robustness subset,
- avoid broad preference language.

### Human Scoring Bias

The solo researcher may introduce subjective scoring decisions.

Mitigation:

- use pre-registered scoring rules,
- maintain a ledger,
- use blinded review for sampled cases if possible,
- report ambiguous cases separately.

---

## 29. Ethics and Responsible Release

This study intentionally creates false or misleading document variants. These artifacts should be clearly marked as synthetic perturbations and kept separate from unmodified benchmark data. Do not release mutated documents without clear warnings and dataset-license review.

Recommended release:

- code,
- prompts,
- scoring scripts,
- aggregate results,
- perturbation metadata when allowed,
- small illustrative examples with clear synthetic labels.

Avoid releasing a dataset that could be confused with accurate source material.

---

## 30. Timeline

### Week 1: Pipeline and Pilot

Day 1:

- Load LongSeal.
- Normalize records.
- Build initial prompt templates and schemas.

Day 2:

- Generate perturbations for 10 to 20 questions.
- Validate with AI agent and human review.

Day 3:

- Run smoke test across 2 responders and 2 evaluators.
- Fix parsing, prompt, and scoring issues.

Day 4:

- Expand to 40-question pilot.
- Run 4x4 model matrix.

Day 5:

- Score pilot.
- Produce first heatmaps.
- Inspect qualitative failures.

### Week 2: Main Short-Run

Day 6 to 7:

- Expand perturbation ledger to 80 to 120 questions.
- Human-validate a sampled subset.

Day 8 to 9:

- Run responder generation.
- Run evaluator judgments.

Day 10:

- Run scoring and statistical analysis.
- Identify failure modes.

Day 11:

- Run style-normalization ablation.
- Run ensemble analysis.

Day 12:

- Human-adjudicate disagreements and featured cases.

Day 13 to 14:

- Write report or short paper draft.
- Prepare figures, tables, limitations, and release artifacts.

### Optional Weeks 3 to 4: Paper Strengthening

- Add sibling evaluators.
- Add more models such as Grok and Llama.
- Run full LongSeal.
- Add prompt robustness checks.
- Add second human annotator for sampled cases.
- Prepare arXiv-style paper.

---

## 31. Budget Strategy

To control cost:

1. Start with a 10-item smoke test.
2. Use low temperature and one generation per item.
3. Cache every API response.
4. Use cheaper models for perturbation drafting and parsing.
5. Reserve expensive frontier models for responder/evaluator matrix calls.
6. Run style-normalization only on a subset.
7. Human-review only strategic samples and disagreements.

Approximate call count for the recommended short paper:

```text
Perturbation drafting and validation: 400 to 800 inexpensive calls
Responder generation: 800 to 1,200 frontier calls
Evaluator judgments: 4,000 to 6,000 judge calls
Parsing/scoring repair: 500 to 1,000 inexpensive calls
```

The exact cost depends heavily on context length. LongSeal contexts may be expensive, so context compression and document selection should be considered only if it does not change the scientific question.

---

## 32. Decision Rules Before Launch

Before running the main experiment, freeze:

1. Model roster.
2. Pairing category definitions.
3. Prompt templates.
4. Perturbation taxonomy.
5. Primary metric.
6. Main statistical contrast.
7. Minimum meaningful effect size.
8. Human adjudication protocol.
9. Exclusion rules.
10. Exact run date window.

Suggested exclusion rules:

- evaluator output is unparsable after two repair attempts,
- context exceeds model limit,
- perturbation invalidated by human review,
- candidate answer abstains and contains no evaluable claims,
- mutation does not create a detectable defect opportunity in the given condition.

Report all exclusions.

---

## 33. Paper Framing

### Candidate Title

Do Models See Their Own RAG Mistakes? Measuring Self- and Cross-Family Blind Spots in LLM-Based Evaluation

### Abstract Claim

We introduce an eval-pairing matrix for RAG that treats the generator-judge relationship as an experimental variable. Using controlled perturbations in long-document QA, we measure whether models are less effective at detecting defects in their own or sibling-family outputs than in cross-family outputs.

### Main Contribution Statement

Unlike prior LLM-as-a-judge work that studies general preference bias, this study examines source-grounded RAG auditing under controlled hidden defects and asks which model pairings produce reliable error detection.

### Practical Takeaway

For RAG systems, evaluator selection should be diversified and validated. Same-model or same-family judging may be acceptable for low-risk smoke tests, but high-stakes factual evaluation should use cross-family judges, claim-level evidence requirements, and human adjudication of uncertain or high-impact cases.

---

## 34. Recommended First Experiment

Start with this exact pilot:

```text
Dataset: 40 LongSeal questions
Perturbations: 2 per question
Responders: GPT-5.4, Sonnet 4.6, Gemini 3.1 Pro, Kimi K2.6
Evaluators: same four models
Arms: answer-perturbation control + source-perturbation arm
Condition: standard source-grounded audit
Ablation: style-normalized audit on 25 percent of answers
Human review: all perturbations, 100 evaluator judgments, all featured examples
Primary metric: defect-level recall
Primary contrast: self vs cross-family
Secondary contrast: sibling vs cross-family if sibling models are available
```

This is small enough to finish quickly and strong enough to reveal whether the signal is real.

---

## 35. What Would Make This Top-Tier

The proposal becomes top-tier if it does three things well:

1. It avoids vague judge preference and measures known hidden defects.
2. It explains self-pairing failures mechanistically, not just descriptively.
3. It turns the results into practical evaluator-selection guidance for RAG systems.

The central intellectual move is to treat evaluation itself as a pairing problem. The evaluator is not a neutral measuring instrument. It has lineage, style, strengths, blind spots, and possibly shared failure modes with the responder. Measuring that matrix directly is the contribution.

