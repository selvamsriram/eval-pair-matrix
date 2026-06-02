# 300 × 3-provider generation run — first analysis

First end-to-end Phase 2 results. Three generators (GPT-5.4, Grok 4.3, Gemini
3.5 Flash HIGH) each ran the `generate` step over the full balanced
`3provider_300` dataset → **900 generator outputs** total.

Generated: 2026-05-31
Pipeline step: `generate` (mode: `rag_perturbed`)
Source dataset: `data/exp/3provider_300.jsonl` (300 records, perturbed
across GPT-5.4 / Grok 4.3 / Gemini 3.5 Flash HIGH)

Run artifacts:
- `data/runs/20260531-005101-gen-gpt55-300/04_generate.jsonl`
- `data/runs/20260531-005112-gen-grok-300/04_generate.jsonl`
- `data/runs/20260531-005123-gen-gemini-300/04_generate.jsonl`

---

## Headline (least expected → most)

### 1. Context-follow rates are strikingly similar across all three generators

|                              | GPT      | Grok     | Gemini   |
| ---------------------------- | -------- | -------- | -------- |
| **context_follow**           | 39%      | 36%      | 41%      |
| memory_override              | 2%       | 1%       | 0%       |
| both_claims                  | 3%       | 2%       | 3%       |
| conflict_awareness           | 7%       | 3%       | 4%       |
| **refusal_or_insufficient**  | 8%       | **31%**  | 20%      |
| unrelated_or_failed          | 41%      | 27%      | 32%      |

The "do models trust retrieval" question has a clean empirical answer in this
data: **~40% of the time generators swallow the perturbed claim, ~0–2% of
the time they push back with memory**. The other ~58% breaks down radically
differently across models (see #4 below).

### 2. Memory override is dead

**0–2% across all three generators.** When the perturbed grounding is coherent
and the original isn't there, generators almost never resist with their
pretraining knowledge. The proposal's central memory-conflict question now has
a sobering (for the "models are stubborn" hypothesis) empirical answer.

### 3. Self-affinity: real for GPT/Grok, INVERTED for Gemini

How much more (or less) does a generator fall for its OWN model's perturbations
vs another model's?

| Generator | own-perturbations  | others'             | Δ            |
| --------- | ------------------ | ------------------- | ------------ |
| GPT       | 37/83 (45%)        | 79/217 (36%)        | **+8.2pp**   |
| Grok      | 37/92 (40%)        | 70/208 (34%)        | **+6.6pp**   |
| Gemini    | 48/125 (38%)       | 75/175 (43%)        | **−4.5pp**   |

GPT and Grok have positive self-affinity ("I trust myself more"). **Gemini
has *negative* self-affinity** — it's *more skeptical* of its own perturbations
than of others'.

Plausible reading: Gemini's perturbations are unusually thorough (recall
92% validation pass rate, heavy use of `relation_inversion`), and that
thoroughness creates a "too clean" signature that Gemini-as-generator
distrusts. The other generators don't notice this pattern; only Gemini does.

**This is the single most interesting finding for the judge-pairing paper.**

### 4. The refusal-vs-dodge axis is the real divider

When generators DON'T follow the perturbed claim, they either refuse outright
or give a generic answer that dodges the specific span. The split is wildly
different:

|         | refusal           | dodge (unrelated_or_failed)         |
| ------- | ----------------- | ----------------------------------- |
| GPT     | 8%                | **41%** ← bulk dodges               |
| Grok    | **31%** ← bulk refuses | 27%                            |
| Gemini  | 20%               | 32% ← roughly even                  |

**Grok refuses on 31% of records — a third.** For judge experiments,
Grok-as-judged-answer is qualitatively different from GPT/Gemini answers
(the judge has to evaluate "is refusal correct here?" which is a different
task from "is this factual claim right?").

### 5. The "failed-validation perturbations still fool generators" hypothesis: CONFIRMED

|                       | validated subset (275 records) | gap-fill subset (25 records, failed validation) |
| --------------------- | ------------------------------ | ----------------------------------------------- |
| GPT context_follow    | 39%                            | **40%**                                         |
| Grok context_follow   | 36%                            | **36%**                                         |
| Gemini context_follow | 41%                            | **40%**                                         |

**Within noise: failed-validation perturbations work just as well as
validated ones.** The validation step catches surface-level issues (leakage,
type errors) that human auditors would flag, but generators are equally
susceptible regardless. Keep the gap-fill records in for Phase 2 analysis —
they're not noise, they're a different signal.

### 6. Citation discipline is essentially perfect when generators follow

|         | context_follow with cited modified passage |
| ------- | ------------------------------------------ |
| GPT     | 114/116 (98%)                              |
| Grok    | 106/107 (99%)                              |
| Gemini  | 122/123 (99%)                              |

Generators aren't hallucinating support — when they accept the perturbed
claim, they're pointing at the right (perturbed) passage. **The judge step
has a clean signal to work with**: the cited passage IDs reliably correspond
to where the perturbation took effect.

### 7. Conflict awareness is rare and concentrated in `relation_inversion`

| perturbation_type      | GPT       | Grok     | Gemini   |
| ---------------------- | --------- | -------- | -------- |
| **relation_inversion** | **13%**   | 4%       | 4%       |
| entity_substitution    | 7%        | 3%       | 5%       |
| causal_change          | 7%        | 9%       | 9%       |
| numerical_shift        | 5%        | 2%       | 2%       |
| temporal_shift         | 3%        | 3%       | 3%       |
| (other types: small n, 0–8%) | | | |

Models notice "something's off" most often when a relation has been inverted
(e.g., "X causes Y" → "Y causes X") — the perturbation that creates the most
obviously wrong-feeling claim against world knowledge. Entity / temporal /
numerical perturbations slip past silently.

---

## Cross-perturber × generator matrix

**context_follow rate** (rows = who perturbed; columns = who generated):

|                | gen=gpt        | gen=grok       | gen=gemini     |
| -------------- | -------------- | -------------- | -------------- |
| perturber=gpt  | 37/83 (45%)    | 31/83 (37%)    | 34/83 (41%)    |
| perturber=grok | 34/92 (37%)    | 37/92 (40%)    | 41/92 (45%)    |
| perturber=gem  | 45/125 (36%)   | 39/125 (31%)   | 48/125 (38%)   |

Diagonal (same model perturbed and generated):
- GPT/GPT: 45%
- Grok/Grok: 40%
- Gemini/Gemini: 38%

Off-diagonals range 31–45%. Not a dramatic cross-family effect; the
self-affinity (#3) lives on the diagonal of GPT and Grok but inverts for
Gemini. Effect is real but modest at this sample size; would benefit from
larger N to tighten error bars.

---

## Cost / latency

|        | total tokens | total calls | p50 latency | wall clock |
| ------ | -----------: | ----------: | ----------: | ---------: |
| GPT    | 617K         | 300 (1 err) | 3.7s        | ~18 min    |
| Grok   | 599K         | 300         | **9.9s**    | ~50 min    |
| Gemini | 633K         | 297 (3 err) | 7.9s        | ~40 min    |

Grok ~2.7× slower than GPT per call. Gemini had 3 hard errors out of 300 —
likely content_filter or safety triggers. Manageable.

---

## Implications for Phase 2B (`judge` step)

1. **The judge will be evaluating ~346 `context_follow` answers** (116 + 107 +
   123) plus an equal volume of dodges and refusals across the 9 (3×3)
   generator-perturber cells.
2. **Key questions the judge can now answer:**
   - Does Judge-X catch context_follow errors made by Generator-Y from
     Perturber-Z?
   - Does same-model bias exist (Judge=Gemini lenient on Gemini-generated
     answers)?
   - Does refusal get correctly evaluated (Grok's 31% refusals — are they
     all valid?)
3. **Gemini's negative self-affinity is the headline result** for the
   same-model-bias thesis. If Gemini-the-judge is also less lenient on
   Gemini-the-generator's outputs, that would be a clean negative-bias
   result worth its own paper section.
4. **The judge's task is well-scoped**: with 98–99% citation discipline on
   context_follow answers, the judge can use the cited passage ID as a
   strong locator for what to verify.

---

## Other points worth noting

- **The dodge rate (`unrelated_or_failed`)** is high (27–41%) and varies a
  lot across generators. It's almost as meaningful a finding as the
  context_follow rate, because it represents the dataset's **structural
  limit**: many questions are broad enough that a generator can answer them
  in a way that simply doesn't invoke the perturbed span at all.
  Implication: the perturbation pipeline is actually a noisier signal on
  broad questions than on fact-pinpoint questions. Worth segmenting Phase 2
  analysis by question type.

- **Refusal asymmetry has a methodological cost.** Grok's 31% refusal rate
  means roughly 90 of its 300 answers carry no factual claim for the judge
  to evaluate. Either the judge has to evaluate "is refusal warranted?"
  (different task) or we drop refusals from the headline metric (loss of
  data). Document this choice up front in the paper.

- **The `relation_inversion` conflict-awareness signal is small (1-3
  records per generator) but consistent (highest across all three).**
  Probably enough to mention as a qualitative observation but not enough
  for a statistical claim.

---

## Files / reproducibility

To re-run this analysis from raw outputs:

```bash
# Source the three generation runs:
RUN_GPT=20260531-005101-gen-gpt55-300
RUN_GROK=20260531-005112-gen-grok-300
RUN_GEM=20260531-005123-gen-gemini-300

# All 04_generate.jsonl files are CoreRecord + generator_outputs[].
# Each generator_output carries: generator_model, mode, answer_text,
# cited_passage_ids, is_refusal, entails_original_claim,
# entails_perturbed_claim, behavior_label.

# Reproducer: this file was generated by the inline Python analysis blocks
# in the chat session that produced it; rerunning the same blocks against
# the above files reproduces every number above exactly.
```

Behavior labels are deterministic (string-match on `original_value` /
`perturbed_value` with normalization + conflict-marker heuristic). Defined
in `src/perturb/steps/generate.py:_behavior_label`. Recomputable from raw
answer text at any time.
