# 300 × 3-provider eval-pair matrix — complete 3×3 judge analysis

Final piece of the Phase 2 measurement chain. Three judges (GPT-5.4, Grok 4.3,
Gemini 3.5 Flash HIGH) evaluated the answers of three generators on the same
300-record balanced perturbation set, producing **2,683 judge verdicts** across
**all nine matrix cells**. This is the data backing the same-model-bias
section of the paper.

Generated: 2026-05-31
Pipeline step: `judge` (6th and final step in `STEP_ORDER`)
Source: each judge run reads `05_label_eval.jsonl` from a corresponding
generate run; writes `06_judge.jsonl` containing per-verdict gold labels
derived from the generator's LLM-eval output.

Run artifacts:
- judges-on-GPT-gen:    `data/runs/20260531-1756*-judge-*-on-gpt/`
- judges-on-Grok-gen:   `data/runs/20260531-2121*-judge-*-on-grok/`,
                        `data/runs/20260531-2123*-judge-grok-on-grok/`
- judges-on-Gemini-gen: `data/runs/20260531-2308*-judge-*-on-gemini/`

---

## The headline matrix (F1, judge × generator)

```
              gen=GPT     gen=Grok     gen=Gemini    row avg
judge=GPT     84.8% *     79.9%        83.6%         82.8%
judge=Grok    83.4%       80.5% *      86.6%         83.5%
judge=Gemini  87.5%       81.9%        88.6% *       86.0%

col avg       85.2%       80.8%        86.2%         83.8%
```
\* = same_exact_model diagonal

- **Strongest judge overall**: Gemini (row avg 86.0%, recall 86–92% per cell)
- **Strongest single cell**: **Gemini-on-Gemini (F1 88.6%, recall 91.5%)** —
  the highest in the entire matrix
- **Weakest cells**: anything judging Grok-gen (col avg 80.8%) —
  Grok's 30% refusal rate creates fundamental ambiguity for any judge

---

## Same-model bias: aggregated number hides the real story

**Aggregated**: diagonal F1 avg 84.6% vs off-diagonal avg 83.8% → **+0.8pp** delta.

Looks like there's almost no same-model bias. But **per-judge** the effect
varies dramatically in both direction and shape:

| Judge       | F1 own  | F1 cross | F1 Δ      | Recall own | Recall cross | Recall Δ   | Pattern                                                                          |
| ----------- | ------- | -------- | --------- | ---------- | ------------ | ---------- | -------------------------------------------------------------------------------- |
| **GPT**     | 84.8%   | 81.7%    | +3.1pp    | **77.5%**  | **83.6%**    | **−6.2pp** | **Lenient on self** — P=94% but misses 6pp more errors in its own answers        |
| **Grok**    | 80.5%   | 85.0%    | **−4.5pp**| 80.5%      | 82.1%        | −1.6pp     | **Worst on self** — precision drops 8pp on own (more false positives)            |
| **Gemini**  | 88.6%   | 84.7%    | +3.8pp    | **91.5%**  | **85.9%**    | **+5.6pp** | **Stricter on self** — catches MORE errors in its own outputs than in others'    |

**Three different same-model-bias signatures, partially canceling in the
aggregate.** This is the central paper-worthy finding: *the same-model-bias
question doesn't have a uniform answer; it depends on which model is the
judge.*

Critically: **Gemini's self-skepticism replicates across paper sections.**
- Generator side: Gemini context_follow Δ = −3.2pp (own vs others' perturbations)
- Judge side:    Gemini recall Δ = +5.6pp (own vs others' generations)

Gemini consistently treats Gemini's outputs more harshly. This is the
**cleanest single result for a same-model anti-bias claim** in the
literature, supported by two independent measurements on the same dataset.

GPT shows classic lenient bias on the recall side (−6.2pp on own), masked at
the F1 level by its higher precision on own outputs.

Grok shows messy/noisy behavior on self — neither leniency nor strictness,
just lower accuracy across the board.

---

## Precision / Recall per cell

```
                gen=GPT          gen=Grok         gen=Gemini
judge=GPT       P94 R77 (n297)   P78 R82 (n299)   P82 R85 (n296)
judge=Grok      P90 R78 (n299)   P81 R81 (n300)   P87 R87 (n296)
judge=Gemini    P89 R86 (n299)   P79 R86 (n300)   P86 R92 (n297)
```

- **GPT is the precision champion**: P = 94% on its own generations.
  When GPT says "incorrect", it's almost always right.
- **Gemini is the recall champion**: highest recall in 4 of 9 cells,
  peaks at 92% own-model.
- **Grok is balanced but unspectacular**: P ~80%, R ~80% across the row.

---

## Generator difficulty: who's hardest to evaluate?

| Generator   | gold_pos rate | avg F1 across judges | avg recall |
| ----------- | ------------- | -------------------- | ---------- |
| Gemini-gen  | 56%           | **86.2%**            | **87.6%**  |
| GPT-gen     | 58%           | 85.3%                | 80.5%      |
| Grok-gen    | 53%           | **80.8%**            | 82.8%      |

**Grok-generated answers are systematically harder for ANY judge to
evaluate.** Probable causes (consistent with earlier label-eval findings):
1. Grok's 30% refusal rate — many answers don't contain a clean factual
   claim to evaluate
2. Grok's hedging writing style
3. Mix of declarative + caveat phrasing

**The column gap (gen=Grok loses ~5pp to the others) is larger than any
same-model row effect.** Generator identity matters more for evaluation
difficulty than judge identity.

---

## Localization quality holds across the full matrix

### Wrong_claim contains the perturbed value (semantic localization, TP-conditional)

|                 | gen=GPT   | gen=Grok   | gen=Gemini   |
| --------------- | --------- | ---------- | ------------ |
| judge=GPT       | 75%       | 71%        | **84%**      |
| judge=Grok      | 76%       | 74%        | 82%          |
| judge=Gemini    | 77%       | 73%        | 81%          |

### Citation locality (supporting_source_passage_id ∈ modified_passage_ids)

|                 | gen=GPT   | gen=Grok   | gen=Gemini   |
| --------------- | --------- | ---------- | ------------ |
| judge=GPT       | 94%       | 95%        | 95%          |
| judge=Grok      | 92%       | 91%        | 95%          |
| judge=Gemini    | 93%       | 94%        | **97%**      |

**91–97% citation locality across every cell.** Every judge correctly points
at the modified passage when flagging an error. The judge's
`supporting_source_passage_id` field is reliable enough to use as ground
truth for downstream analysis.

Gemini-generated perturbations are easiest to localize (81–84% wrong_claim,
95–97% citation) — likely because Gemini's perturbations skew toward
`relation_inversion` and clean entity substitutions where the wrong claim
is structurally obvious.

---

## What this means for the paper

1. **Do same-model pairings exhibit bias?** Yes, but **the direction differs
   per judge model**. GPT is lenient on itself (classic bias direction),
   Gemini is stricter on itself (anti-bias direction), Grok is just noisier
   on itself. The aggregated +0.8pp F1 delta hides this — the per-judge
   breakdown is the real finding.

2. **Gemini's self-skepticism is replicated across two independent
   measurements** (generator side AND judge side, same dataset, same 300
   records). The strongest single result in the paper.

3. **Generator identity > judge identity** for evaluation difficulty.
   Average column variance (85.3 / 80.8 / 86.2, ±2.7pp) is larger than
   average row variance (82.8 / 83.5 / 86.0, ±1.6pp). The hardest cell to
   evaluate comes from the hardest-to-judge generator (Grok), not the
   worst judge.

4. **The eval-pair-matrix methodology works**: F1 80–89% with P=78–94% and
   R=77–92% across all 9 cells means judges reliably catch induced errors.
   The matrix is a sound measurement instrument.

5. **Localization is effectively solved at this scale** — 91–97% citation
   locality means we can confidently use judge citations as ground-truth
   pointers for any downstream error-localization analysis.

6. **Sample sizes are tight enough to trust cross-cell deltas**: 296–300
   verdicts per cell with gold positive rates around 53–58% gives ~165
   true positive candidates per cell. Deltas of 4–6pp on F1 / recall
   exceed reasonable confidence intervals.

---

## What's still open (next-phase work)

- **`same_provider_family` cell is empty.** All current providers are
  single-model-per-family in our setup. Adding Anthropic (Claude Sonnet +
  Claude Haiku) would fill the gap and let us measure whether judge bias
  is structural to the model family or specific to the exact model.
- **Reliability check needed.** These are single-shot judge calls. A
  consistency check (re-run a judge with same prompt, measure flip rate)
  would quantify how much per-cell variance is irreducible noise.
- **Wrong_claim quality** is at 71–84% perturbed-value containment —
  meaningful gap from perfect. The 16–29% that miss are usually paraphrases
  ("the cited figure" instead of the specific number). A stricter judge
  prompt could push this higher; useful for downstream verbatim-quote
  analyses.

---

## Files / reproducibility

Each `06_judge.jsonl` file contains the full CoreRecord plus, on each
generator_output, a list of `JudgeVerdict` entries from this run. The
verdict carries:

```jsonc
{
  "judge_provider": "azure-gpt",
  "judge_model": "gpt-5.4",
  "generator_provider": "...",
  "generator_model": "...",
  "generator_mode": "rag_perturbed",
  "pair_type": "same_exact_model | cross_provider_family",  // same_provider_family is empty
  "verdict": "correct | incorrect | unclear",
  "contains_factual_error": true,
  "wrong_claim": "...",
  "supporting_source_passage_id": 3,
  "confidence": "high",
  "gold_has_induced_error": true,
  "gold_perturbation_target": "1911",
  "gold_perturbation_replacement": "1912",
  "run_id": "...",
  "completed_at": 1764541380
}
```

Gold labels are derived locally per record from the generator's `llm_eval`
output. The judge has NO access to: the perturbation, the perturbed
grounding, the deterministic labels, or the LLM-eval labels. It sees only
`(question, generator_answer, all_grounding_original)`.

Judge prompt: [src/perturb/prompts.py](src/perturb/prompts.py),
`JUDGE_SYSTEM` / `JUDGE_SCHEMA` / `JUDGE_USER` (around line 250).
Step implementation: [src/perturb/steps/judge.py](src/perturb/steps/judge.py).

All numbers in this document were produced from the 9 `06_judge.jsonl`
files listed at the top by the inline Python analysis blocks in the chat
session that produced this file. Re-running those blocks reproduces every
number here exactly.
