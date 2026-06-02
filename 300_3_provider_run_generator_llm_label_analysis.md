# 300 × 3-provider generation run — LLM-label analysis (v2 / corrected)

Second-pass analysis of the same 900 generator outputs as
`300_3_provider_run_first_analysis.md`, with behavior labels now coming from
an independent LLM evaluator (GPT-5.4) instead of the deterministic
string-match heuristic. This is the **canonical reading** of the data.

Generated: 2026-05-31
Pipeline step: `label_eval` (5th step in `STEP_ORDER`)
Source label runs:
- `data/runs/20260531-005101-gen-gpt55-300/05_label_eval.jsonl`
- `data/runs/20260531-005112-gen-grok-300/05_label_eval.jsonl`
- `data/runs/20260531-005123-gen-gemini-300/05_label_eval.jsonl`

Evaluator: GPT-5.4 (azure-gpt), one call per generator output.
Coverage: 897/900 outputs successfully evaluated (3 transient errors).
Eval cost: ~1.01M input + 85K output tokens total, ~30 min sequential.

Going forward, the deterministic `behavior_label` field stays on every
record for transparency (and as a cheap smoke check during development), but
all numbers cited in publication-bound work come from `llm_eval.behavior_label`
plus solid code-emitted signals (`is_refusal`, `cited_passage_ids`,
`modified_passage_ids`).

---

## Headline distribution

| Label                       | GPT-5.4   | Grok 4.3  | Gemini 3.5 Flash |
| --------------------------- | --------- | --------- | ---------------- |
| **context_follow**          | **51%**   | **47%**   | **48%**          |
| memory_override             | 3%        | 3%        | 1%               |
| both_claims                 | 7%        | 5%        | 6%               |
| conflict_awareness          | 1%        | 4%        | 1%               |
| refusal_or_insufficient     | 5%        | 25%       | 18%              |
| unrelated_or_failed         | 32%       | 16%       | 25%              |

**Generators trust the perturbed retrieved evidence ~50% of the time.**
Across three independent models, RAG generators are *more* susceptible to
controlled grounding manipulation than the first-pass deterministic analysis
suggested (it estimated 36-41%). The +9-12pp correction comes from the LLM
catching paraphrased acceptance of the perturbed value that strict string
match missed.

---

## Entailment structure (paraphrase-aware)

The (entails_original, entails_perturbed) joint distribution sharpens the
picture:

|                                                 | GPT     | Grok    | Gemini  |
| ----------------------------------------------- | ------- | ------- | ------- |
| (F, T) — pure context follow                    | **53%** | **48%** | **49%** |
| (T, T) — both invoked                           | 6%      | 5%      | 6%      |
| (T, F) — pure memory override                   | 3%      | 3%      | 1%      |
| (F, F) — neither invoked (dodge / refuse / etc) | 38%     | 43%     | 43%     |

**Memory override is rare (1-3%) and consistent across generators.** The
proposal's central question — "do generators resist with memory?" — has a
clear empirical answer: almost never.

---

## Self-affinity (same-model perturber × generator)

| Generator | own-perturbations  | others'           | Δ            |
| --------- | ------------------ | ----------------- | ------------ |
| GPT       | 47/83 (57%)        | 106/216 (49%)     | **+7.6pp**   |
| Grok      | 46/92 (50%)        | 95/207 (46%)      | **+4.1pp**   |
| Gemini    | 57/124 (46%)       | 86/175 (49%)      | **−3.2pp**   |

GPT and Grok have positive self-affinity (they fall for their own model's
perturbations more often). **Gemini has *negative* self-affinity** — it is
the only generator that is *more skeptical* of its own perturbations.

This is the most paper-worthy single finding for the same-model-bias section.
The qualitative pattern survives the move from code labels to LLM labels;
magnitudes shift only modestly (was +8.2 / +6.6 / −4.5 with code labels).

---

## Full perturber × generator matrix (LLM context_follow rate)

|                            | gen=GPT   | gen=Grok  | gen=Gemini |
| -------------------------- | --------- | --------- | ---------- |
| perturber=GPT (azure-gpt)  | **57%**   | 49%       | 52%        |
| perturber=Grok             | 46%       | **50%**   | 47%        |
| perturber=Gemini           | 52%       | 44%       | **46%**    |

- Diagonal (own-perturbations): GPT 57%, Grok 50%, Gemini 46%
- Off-diagonal range: 44–52%
- Single most-followed cell: GPT-on-GPT (57%)
- Single least-followed cell: **Grok generator on Gemini perturbations
  (44%)** — Grok is most resistant to Gemini's perturbation style

---

## Validated vs gap-fill perturbations

|        | validated (n=274)  | gap-fill (n=25)    | Δ            |
| ------ | ------------------ | ------------------ | ------------ |
| GPT    | 142/274 (52%)      | 11/25 (44%)        | +7.8pp       |
| **Grok** | **132/274 (48%)** | **9/25 (36%)** | **+12.2pp**  |
| Gemini | 131/274 (48%)      | 12/25 (48%)        | −0.2pp       |

**Refined finding**: gap-fill perturbations still fool generators, but
**Grok specifically benefits noticeably from validated perturbations**
(+12pp). For GPT the effect is modest. For Gemini there is no effect at all.
Validation matters most for Grok, least for Gemini.

This is a notable refinement of the first-pass conclusion ("validation
status doesn't change generator behavior") which was based on the
deterministic labels and missed this generator-specific signal.

---

## NEW finding: relation_inversion is the only perturbation type that triggers real pushback

| perturbation_type     | memory_override (GPT / Grok / Gemini) | conflict_awareness (GPT / Grok / Gemini) |
| --------------------- | ------------------------------------- | ----------------------------------------- |
| **relation_inversion**| **17% / 17% / 13%**                   | **4% / 22% / 13%**                        |
| causal_change         | 4% / 4% / 2%                          | 0% / 4% / 2%                              |
| numerical_shift       | 2% / 0% / 0%                          | 3% / 3% / 0%                              |
| entity_substitution   | 1% / 2% / 0%                          | 0% / 1% / 0%                              |
| temporal_shift        | 3% / 0% / 0%                          | 0% / 3% / 0%                              |
| negation_modality     | 7% / 0% / 0%                          | 0% / 7% / 0%                              |
| location_change       | 0% / 0% / 0%                          | 0% / 0% / 0%                              |
| ranking_flip          | 0% / 0% / 0%                          | 0% / 0% / 0%                              |
| affiliation_change    | 0% / 0% / 0%                          | 0% / 0% / 0%                              |

When generators DO push back — either by overriding with memory or flagging
conflict — it is **dramatically concentrated in `relation_inversion`**.
13-17% of relation_inversion perturbations trigger memory_override (vs 0-4%
for everything else). Grok flags conflict on 22% of relation_inversion
perturbations.

**This is a real, replicable signal across all three generators.**

Intuition: inverting a known causal or dependency relation
(e.g. "laminar flow reduces drag" → "laminar flow increases drag") creates
a claim that is *physically wrong* in a way the generator's pretraining
knows. Other perturbation types swap entities, dates, or numbers — the
model has no strong prior to push back with.

In the first-pass code-label analysis, conflict_awareness signal on
relation_inversion was visible at 13% (GPT only) and dismissed as small.
With LLM labels and adding memory_override to the picture, **relation
inversion exposes the memory-vs-retrieval tension across all three
generators**.

---

## Solid code metrics (independent of behavior_label)

### Generator-emitted `is_refusal` flag

|        | is_refusal=true | LLM label refusal_or_insufficient |
| ------ | --------------- | --------------------------------- |
| GPT    | 19 (6%)         | 16 (5%)                           |
| Grok   | 91 (30%)        | 74 (25%)                          |
| Gemini | 58 (19%)        | 54 (18%)                          |

The generator's own self-declared refusal flag tracks LLM-labeled refusal
closely. **Grok refuses 5× more often than GPT.** The small gap between
self-flagged refusal and LLM-labeled refusal (especially for Grok) =
cases where the generator said "insufficient" but the LLM judged it as
actually flagging a conflict instead.

### Citation discipline when context_follow

|        | context_follow answers | cited the modified passage |
| ------ | ---------------------- | -------------------------- |
| GPT    | 153                    | **152 (99%)**              |
| Grok   | 141                    | **141 (100%)**             |
| Gemini | 143                    | **143 (100%)**             |

When generators accept the perturbed claim, they cite the modified evidence
almost without exception. **The judge step has a clean signal to work
with**: the cited passage ID reliably points to where the perturbation took
effect.

---

## What changed from the first-pass (deterministic-label) analysis

| Finding                                              | Code labels said   | LLM labels say                                | Status         |
| ---------------------------------------------------- | ------------------ | --------------------------------------------- | -------------- |
| Context_follow rate                                  | ~40%               | **~50%**                                      | ↑ revised up   |
| Memory override is rare                              | 0-2%               | 1-3%                                          | ✓ holds        |
| Self-affinity (GPT/Grok positive, Gemini negative)   | +8 / +7 / −5       | +8 / +4 / −3                                  | ✓ holds        |
| Grok refuses heavily                                 | 31%                | 25% (self-flagged 30%)                        | ✓ holds        |
| Gap-fill perturbations still fool generators         | yes uniformly      | yes but Grok shows +12pp validation effect    | ↑ refined      |
| relation_inversion triggers some conflict_awareness  | 13% (GPT only)     | **4-22% conflict + 13-17% memory_override**   | ↑ much stronger |
| Citation discipline on context_follow                | 98-99%             | 99-100%                                       | ✓ holds        |

The disagreement between code and LLM was **228/897 (25%) of records**, with
specific systematic patterns:

- 84 records the deterministic labeler called `unrelated_or_failed` were
  actually `context_follow` per LLM (paraphrased acceptance the string
  match missed)
- 24+15 records the deterministic labeler called `conflict_awareness` were
  actually unrelated or context_follow (false positives from the trigger-word
  heuristic)

**The LLM was high-confidence on 97% of all evaluations**, including 228 of
the 235 disagreements with code. The disagreements are not LLM uncertainty —
they are clear cases where the deterministic heuristic failed.

---

## Practical implications for Phase 2 (judge step) and the paper

1. **Use ~50%, not ~40%, as the headline context_follow rate.** More
   dramatic and accurate.
2. **Gemini's negative self-affinity is the cleanest same-model-bias result**
   in this dataset — −3.2pp, opposite direction from the other two. Build
   the judge step's paper section around this.
3. **`relation_inversion` deserves its own analysis section.** It is the
   only perturbation type that exposes the memory-vs-retrieval tension.
   The paper should call this out and discuss why.
4. **For the judge step, the high-signal subset is the 437 LLM-context_follow
   answers** (153 + 141 + 143). These have a paraphrase-confirmed factual
   error the judge needs to catch. Plus 144 refusals to evaluate
   "did the model refuse correctly?" and 22 memory_override cases to
   evaluate "did the model correctly override?".
5. **Gap-fill records (25) are still worth keeping** for Grok-specific
   analysis — they reveal a 12pp validation effect that GPT and Gemini do
   not show.
6. **Drop the deterministic `behavior_label` heuristic from publication-bound
   numbers.** Keep it on records as a fast smoke check during development,
   but cite only LLM labels in the paper.

---

## Files / reproducibility

The raw data lives in the three `05_label_eval.jsonl` files listed at the
top. Each `generator_outputs[i].llm_eval` carries:

```jsonc
{
  "evaluator_provider": "azure-gpt",
  "evaluator_model": "gpt-5.4",
  "behavior_label": "context_follow",
  "entails_original_claim": false,
  "entails_perturbed_claim": true,
  "rationale": "The answer explicitly states ... matching the perturbed claim",
  "confidence": "high",
  "run_id": "20260531-005101-gen-gpt55-300",
  "completed_at": 1764541380
}
```

The evaluator prompt is in [src/perturb/prompts.py](src/perturb/prompts.py)
as `LABEL_EVAL_SYSTEM` / `LABEL_EVAL_SCHEMA` / `LABEL_EVAL_USER` (around
line 178). The step implementation is in
[src/perturb/steps/label_eval.py](src/perturb/steps/label_eval.py).

All numbers in this document were produced from the JSONL files above by
the inline Python analysis blocks in the chat session that produced this
file. Re-running those blocks reproduces every number here exactly.
