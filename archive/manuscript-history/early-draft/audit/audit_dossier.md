# Eval-Pair-Matrix — Audit Dossier

**For:** the research assistant writing the revised paper.
**Purpose:** a complete record of everything we did in the re-analysis and human audit, the reasoning behind each step, the numbers (with where they come from), and what each result means for the manuscript. Read this top-to-bottom once; then use it as the reference while writing.

**Companion files**
- `cell_audit_findings.md` — auto-generated coverage grid, per-cell tallies, bounds, gold-quality, **and the full per-case adjudication log** (regenerate with `gen_audit_dossier.py`).
- `paired_audit_summary.md` / `paired_audit_report.json` — the paired statistical analysis (Agent 1).
- `behavior_stratified_report.json` + `../tables/behavior_stratified.tex` — the step-6-by-step-5 table.
- `cell_audit_findings.json`, `../tables/cell_audit_summary.tex` — audit numbers/tables.
- `archive_fpr_review/` — a superseded first-pass audit tool + its 34 judgements (kept for provenance; **not** part of the final analysis).

> **One-line takeaway for the paper:** raw diagonal-vs-off-diagonal differences in the judge matrix are tiny; after a paired, answer-level analysis there is **no robust same-deployment effect on recall** but a robust difference in *flagging of target-negative answers*; a human audit shows those "false positives" are **essentially never genuine false alarms** — they are real source-errors the judge caught or gold-label mistakes — so the effect is a **labeling artifact (Case C)**, not judge self-leniency.

---

## 1. Why we did any of this (the central objection)

The paper studies LLM-as-judge for RAG factuality with a fully-crossed **3×3 judge×generator matrix**. The original headline was "same-model bias": each judge's diagonal cell (e.g. GPT judging GPT) was compared against that judge's **off-diagonal** cells (GPT judging Grok/Gemini).

The Round-1 reviewer's central objection: **off-diagonal cells are different answers** with different length, style, refusal rate and difficulty, so a diagonal-vs-off-diagonal gap conflates same-model bias with generator difficulty. Their smoking gun: on GPT's answers, GPT-judge recall = 77.5% and **Grok**-judge recall = 77.7% — nearly identical — so GPT-judge is not uniquely lenient on GPT answers. The claimed −6.2 pt "GPT self-leniency" came from comparing GPT-on-GPT to GPT-on-*other* answers, not from comparing judges on the *same* answers.

Everything below is the fix.

---

## 2. The reframed research question (estimand)

Replace *"does a judge behave differently on its own model's outputs?"* with:

> **On the exact same candidate answer, does the matching judge behave differently from the non-matching judges?**

Terminology to use in the paper:
- **"same-deployment pairing effect"**, not "same-model-family bias" (one exact deployment per provider; cannot separate exact-model / provider-family / style-familiarity).
- **"target-negative flagged" / "apparent false positive"**, not "false positive" (gold tracks only the planted error — see §4).

---

## 3. Agent 1 — the statistical rescue (paired, answer-level)

**Script:** `paired_audit.py` → `paired_audit_summary.md`, `paired_audit_report.json`, `../tables/{validated_matrix,paired_effects}.tex`. Read-only over the JSONL.

**Method.** Every candidate answer was judged by all three judges, so for each answer we compare the **matching** judge against the **mean of the two non-matching** judges *on that same answer*: `delta = same_pred − cross_mean`. Averaged over gold-positive answers → **recall Δ**; over gold-negative answers → **FPR Δ**; over all → **flag-rate Δ**. Uncertainty: **cluster bootstrap by `core_id`** (the question), resampling each dataset's own cluster population — **275 validated cores** for the primary, 300 for full, 25 for gap-fill; 10,000 replicates; 95% percentile CIs. (We initially resampled 300 for the validated estimand and corrected it to 275 — the principled match to "the 275 validated records are the benchmark.")

**Primary results (275 validated records):**

| Contrast | Δ (pp) | 95% CI | verdict |
|---|---|---|---|
| Recall (gold-positive) | **−0.5** | [−2.7, +1.7] | **null** |
| False-positive rate (gold-negative) | **−4.3** | [−6.6, −2.0] | **robust** |
| Flag-rate (all) | **−2.2** | [−3.8, −0.6] | robust |

The validated 3×3 matrix is nearly flat on the diagonal: mean diagonal F1 **84.4** vs off-diagonal **83.4** (+0.9). So:
- The original "self-leniency lets a judge miss its own model's errors" claim is **not supported** once difficulty is controlled (recall null).
- There **is** a robust same-deployment difference on **target-negative** answers (matching judge flags fewer). Interpreting *that* difference is the entire job of the audit.

**Make the 275 validated records primary** (only 275 of 300 pass all five validation gates); report the 25 as a failed-validation diagnostic.

---

## 4. The two-layer judge architecture & where "gold" comes from

There are **two distinct LLM-evaluation layers** over the answers — keep them separate in the writing:

| | **Layer 1 — label-evaluator** (`05_label_eval`) | **Layer 2 — judges** (`06_judge`) |
|---|---|---|
| Model(s) | **one fixed model: GPT-5.4 (`azure-gpt`)** | GPT, Grok, Gemini (the 3×3 matrix) |
| Task | behavior label + `entails_perturbed_claim` | `contains_factual_error` (any error vs source) |
| Sees | answer **+ the perturbation** | only question + answer + **original** passages (blind to the perturbation/gold) |
| Role | **produces the gold** | the system under test |
| Output field | `generator_outputs[].llm_eval` | `judge_verdicts[]` |

**Where `gold_has_induced_error` comes from:** it is the Layer-1 model's `entails_perturbed_claim`, carried into each judge verdict. Verified: `gold == entails_perturbed_claim` for **2662/2683** verdicts (the 12 exceptions are stricter — `both_claims` answers entail both, set to gold-False). The label file has no gold field of its own; gold is *derived* from the entailment flag.

**Two consequences to state explicitly:**
1. **The gold is single-model (GPT).** Judges — including GPT-judge — are scored against a GPT-made gold. This does **not** confound the *paired* same-vs-cross delta (all three judges share the same gold per answer, so it cancels), but it can bias absolute base rates, and for some cells **GPT made the gold and GPT was the judge**.
2. **"FP" is defined only against the planted target.** The gold is "did the answer adopt the planted false value?" The judge's actual task is "is there *any* factual error vs the source?" So a "false positive" is a *target-negative flag* — it can be (a) a real false alarm, (b) the judge catching a **different** real error, or (c) a **gold mislabel**. Untangling these is the audit.

---

## 5. The label-evaluator's reliability (a real limitation)

Because behavior label *and* `entails_perturbed` come from the **same Layer-1 call**, they can — and do — contradict each other:

- **15 of 897 labeled outputs (1.7%)** are internally self-contradictory (behavior implies one thing about adoption, `entails_perturbed` says the opposite).
- The direction is lopsided: **14 are "non-adopting behavior (refusal/conflict) but `entails_perturbed=True`"** → these become **spurious gold-positives** (refusal 9, conflict 5). Only 1 is the reverse.
- These spurious gold-positives are exactly the confusing `conflict_awareness/TP` and `refusal/TP` cells.

**Heuristic the RA should mention:** when behavior is non-adopting (refusal/conflict/unrelated/memory) but the cell is TP/FN, it's a prime gold-mislabel candidate. The human audit confirmed several of these.

---

## 6. Behavior-stratified analysis (step 6 by step 5) — the table that explains the matrix

**Script:** `behavior_stratified.py` → `behavior_stratified_report.json`, `../tables/behavior_stratified.tex`. Validated set, pooled over all 9 cells, **behavior = `llm_eval` only**, cluster-bootstrap CI **by answer**.

| Generator behavior | verdicts | answers | TP | FP | FN | TN | headline rate [95% CI] |
|---|---|---|---|---|---|---|---|
| context_follow (adopts false value) | 1212 | 405 | 1025 | 0 | 187 | 0 | **recall 84.6% [81.5, 87.6]** |
| both_claims | 135 | 45 | 88 | 0 | 44 | 3 | recall 66.7% [54.5, 78.8] |
| memory_override (uses true value) | 42 | 14 | 0 | 0 | 0 | 42 | **FPR 0.0% [0, 7.1]** |
| conflict_awareness | 54 | 18 | 3 | 46 | 0 | 5 | **FPR 90.2% [76.5, 100]** |
| refusal_or_insufficient | 400 | 134 | 23 | 130 | 1 | 246 | FPR 34.6% [27.4, 42.2] |
| unrelated_or_failed | 606 | 202 | 0 | 25 | 0 | 581 | FPR 4.1% [2.1, 6.3] |
| *unlabeled (no llm_eval)* | 9 | 3 | 0 | 8 | 0 | 1 | *FPR 88.9%* |

Totals: 2458 validated verdicts; TP 1139, FP 209, FN 232, TN 878.

**Reading:** recall is concentrated entirely in committed answers (context_follow supplies 1025/1139 TP); the **false positives are concentrated in refusal (130) + conflict (46) = 176/209 (84%)**, plus unrelated (25) and unlabeled (8); memory_override is a clean control (0 FP). And the same-deployment FPR effect from §3 lives **entirely in refusals/hedges**: stratified paired FPR Δ was ~0 on engaged answers, **−6.2 pp on refusal+conflict** (n=146), −3.2 on unrelated.

**A defect we found and fixed (worth a methods footnote).** The first version silently folded **9 unlabeled verdicts (3 answers)** into the refusal row (a fallback to the generator's self-reported label when `llm_eval` was missing). Corrected: behavior = `llm_eval` only; the 9 are a separate UNLABELED row (they flag 8/9 of the time). We also added **cluster-by-answer CIs** and a **rule-of-three** bound for the zero-event memory_override row. Old refusal numbers (n=409, FPR 36%) → correct (n=400, FPR 34.6%); "88% of FPs are refusal/conflict" → **84%**.

---

## 7. The human cell audit (the new primary evidence)

### 7.1 Why and how
Question Agent 1 left open: when a judge flags a target-negative answer, **is it wrong, or did it catch a different real error?** We built a per-cell review: for every (behavior × {TP, FP, FN, TN}) group we sampled **up to 12 cases** (all if fewer; seed 20260627), **153 cases** across 17 populated cells. Tool: `cell_review_app.py` + `cell_review_dashboard.html`; judgements auto-save to `cell_review_progress.json`.

> Call this a **"targeted author audit / manual adjudication sample"** in the paper — a single adjudicator, not independent human annotation.

### 7.2 Codebook — the two calls per case
Per case the adjudicator records exactly two things; everything else is derived.

- **`human_gold_ok`** (yes/no/unclear) — *is the gold label correct?*
  - gold-positive cells (TP/FN): did the answer **adopt** the perturbed (false) value **as its answer**?
  - gold-negative cells (FP/TN): did the answer **avoid adopting** the false value?
- **`human_judge_ok`** (yes/no/unclear) — *did the judge make the right flag / no-flag call vs the **original** passages?*

**The single most important rule (it caused a real bug we fixed): ADOPT ≠ MENTION.** Gold-negative means the answer did **not commit** to the false value. A conflict-aware or refusing answer can **quote** the false value, list it among conflicting figures, or name it while refusing, and still be correctly gold-negative. Only mark `gold_ok = no` on a gold-negative case if the answer actually **asserts the false value as its answer** (then it's a mislabel that should be a TP).

**Derivation table `(cell, gold_ok, judge_ok) → verdict`:**

| Cell | gold_ok | judge_ok | meaning |
|---|---|---|---|
| TP | yes | yes | genuine true positive |
| TP | no | — | gold mislabel (didn't actually adopt) |
| TP | yes | no | right verdict, wrong reason (judge flagged, not for the planted error) |
| FP | yes | no | **genuine false alarm** (the only "real" FP) |
| FP | yes | yes | judge caught a **real / alternate** error the target-gold ignores |
| FP | no | — | gold mislabel (answer DID adopt → really a TP) |
| FN | yes | no | genuine miss |
| FN | no | — | gold too aggressive (answer didn't actually adopt) |
| TN | yes | yes | genuine true negative |
| TN | — | no | judge **missed** a real error |
| TN | no | — | gold mislabel (answer DID adopt) |

### 7.3 Subtleties & traps (write these into Methods/Limitations)
1. **The meta-claim artifact.** A refusal/conflict answer that comments on the source (*"the passages don't say X, they say Y"*) is reporting what its **perturbed** passages said; the judge checks against the **original** passages and flags the mismatch. Whether that counts as "the judge caught a real error" or "an artifact of the original-vs-perturbed scoring" is a genuine interpretive call (see #3).
2. **Adopt ≠ mention** (above) — the dominant trap; the dashboard help text originally got this wrong and was corrected.
3. **The strict source-grounding stance.** The adjudicator resolved the artifact question by ruling: if the answer's claim **contradicts the original passages**, the judge was right to flag (`judge_ok = yes`), even when the answer faithfully reported the perturbed source. This is a deliberate, defensible choice — and it is what makes the FP cases come out as "judge caught a real error" rather than "artifact." **State this stance explicitly**; it is load-bearing.
4. **Behavior ⟂ gold contradictions** (§5) surface as confusing cells where a "conflict"/"refusal" answer is gold-positive. Judge the gold on its merits (adopt vs not), not the behavior tag.

### 7.4 Worked cases (including where our first reads were wrong)
- **Conflict FP — Bitcoin/S&P (`GPT-on-Grok__b4320327f5ee`), 28%→15%.** Answer lists *inconsistent* figures incl. "15%". gold_ok=**yes** (listed, not adopted); judge_ok=**yes** (the "passages report 15%" claim contradicts the original 28%). *Reversal: the analyst first called this an artifact/false alarm; the adjudicator's strict-grounding call (real error) was adopted.*
- **Conflict TP — explainability/RL (`GPT-on-Grok__4c6f5c875224`), explainability→standardization.** Answer: "passages don't discuss explainability… they **emphasize standardization** as a key factor." gold_ok=**yes** (it does adopt standardization). *Reversal: the analyst first leaned `gold_ok=no` off the refusal-style opener; on reading the full clause it adopts the false value → yes.* Also a §5 behavior⟂gold case (tagged conflict, but entails_perturbed=True).
- **Cross FP — SEC/ASC-842 (`Grok-on-GPT__1ed95f043a07`), the paper's Table 7 example.** Answer misattributes ASC 842 to the SEC; judge flags "FASB, not SEC." gold_ok=yes (didn't adopt the planted phrase), judge_ok=yes — a clear **alternate valid error** the target-gold scored as an FP.
- **Refusal FP gold-mislabels.** Several refusal-labeled answers actually adopted the false value → `gold_ok=no`, "really a TP" — the §5 contradiction confirmed by eye.

### 7.5 Coverage & findings
Live numbers + the **full per-case log** are in `cell_audit_findings.md`. As of the last regeneration (**88 / 153 reviewed**):

| Cell | n | result | same / cross |
|---|---|---|---|
| **FP** | 25 | **0 genuine false alarms** (23 real/alternate errors, 2 gold-mislabels→TP) | same 9/9, cross 16/16 judge-correct |
| **TN** | 31 | **0 missed errors** (31/31 genuine) | same 14/14, cross 17/17 |
| **TP** | 23 | 21 genuine (1 right-verdict-wrong-reason, 1 gold mislabel) | — |
| **FN** | 9 | **6 genuine misses**, 3 gold-too-aggressive | — |

Bounds (rule of three): FP false-alarm rate **0/25, ≤ ~12%**; TN missed-error rate **0/31, ≤ ~10%**. Gold-label issues: **7/88 (~8%)**, all in refusal/conflict, in **both** directions.

---

## 8. Synthesis — what it all means

1. **No robust same-deployment recall effect** (Δ −0.5 pp, CI crosses 0). Drop the "self-leniency misses its own errors" claim.
2. **The apparent-FP metric does not measure judge error.** 0/25 audited FPs were genuine false alarms; they are real source-errors the judge caught or gold mislabels. → **Case C**: the FPR difference is a **target-only-gold labeling artifact**, not judge over-flagging/leniency.
3. **Judges are simply accurate on gold-negative answers** — right whether they flag (25/25) or stay silent (31/31), with **no same-vs-cross correctness difference**. So the FPR *gap* (same flags fewer) cannot be "same judges are wrong less"; both are right. Its mechanism (does same miss what cross catches on the **same** answer?) is **not** resolved by this per-cell sample — that needs an answer-paired follow-up and is a stated limitation.
4. **Recall is real and slightly under-measured.** TP genuine (21/23); FN are mostly genuine misses (6/9) but **3/9 are gold-too-aggressive**, so the 84.6% recall is a mild *under*estimate.
5. **Generator behavior, not provider identity, drives the matrix.** Recall lives in context_follow; FPs live in refusal/conflict; the same-deployment FPR effect is entirely a refusal/conflict phenomenon (style-familiarity, which the design cannot separate from self-preference).
6. **The gold (Layer-1, single GPT) is imperfect** — 1.7% internally self-contradictory, ~8% audited error in refusal/conflict, both directions.

**Suggested abstract sentence:** *Across a fully crossed 3×3 matrix, raw diagonal differences are small (mean diagonal F1 84.4 vs off-diagonal 83.4). After a paired, answer-level analysis on 275 validated records we find no robust same-deployment effect on recall (Δ −0.5 pp, 95% CI [−2.7, +1.7]); the one robust difference is in flagging of target-negative answers, but a targeted audit shows those flags are essentially never false alarms — they are real source-errors or gold-label mistakes — so the effect is a labeling artifact rather than judge self-leniency. Generator behavior and answerability explain most of the matrix variation.*

---

## 9. Limitations (put these in the paper)
- **Single adjudicator** ("targeted author audit"), not independent human annotation with κ/α.
- **Per-cell random sample, not answer-paired** — establishes that judges are accurate on gold-negatives, but **not** the exact same-vs-cross mechanism of the FPR gap.
- **Single-model (GPT) gold** for both the behavior labels and the induced-error label; 1.7% internally self-contradictory; ~8% audited error in refusal/conflict.
- **One exact deployment per provider** — cannot separate exact-model, provider-family, and style-familiarity effects.
- **Single-shot judging** (no stochastic-flip estimate).
- The audit's "judge caught a real error" rests on the **strict source-grounding** stance (§7.3 #3); a stricter "artifact" reading would move some FP cases from "alternate error" toward "artifact," but **not** toward "false alarm" — the 0-false-alarm result is robust to that choice.

---

## 10. Implications mapped to the manuscript
- **Abstract / contributions:** lead with the controlled null + the labeling-artifact reframing (§8). Reduce 5 contributions to 3 (protocol; crossed+paired benchmark; controlled findings).
- **Methods:** add the two-layer description (§4), gold provenance, exact deployment IDs (GPT `gpt-5.4`, Grok `grok-4.3`, Gemini `gemini-3.5-flash`), the label-evaluator (`gpt-5.4`).
- **Results:** paired matrix + effects (§3); behavior-stratified table (§6); audit results (§7.5) → Case C.
- **Limitations:** §9 verbatim-ish.
- **Related work to add:** Chen et al. 2025 (no overarching self-preference in fact-centric RAG — closest prior); **ContextualJudgeBench** (refusal correctness/faithfulness — directly relevant to the refusal-driven FP story); REFLECT; RAGferee; update GaRAGe to Findings-of-ACL 2025.
- **Framing:** "full matrices are useful, but raw diagonal-vs-off-diagonal comparisons mislead unless generator difficulty and answer-level pairing are controlled" — more defensible and general than three provider "personalities."

---

## 11. Reproducibility — files, scripts, seeds
All scripts are **read-only over the raw JSONL** under `data/` and write only audit outputs.

| Script | Produces | Notes |
|---|---|---|
| `paired_audit.py` | paired effects + matrices + CIs | bootstrap seed 20260627, 10k reps, resample by core_id |
| `behavior_stratified.py` | step-6-by-step-5 table | behavior = `llm_eval` only; CI by answer; rule-of-three for 0-event |
| `build_cell_review_queue.py` | `cell_review_queue.{json,csv}` | seed 20260627, cap 12/cell |
| `cell_review_app.py` | the dashboard + autosave + summary/tex | progress in `cell_review_progress.json` |
| `gen_audit_dossier.py` | `cell_audit_findings.{md,json}` | coverage, tallies, bounds, gold-quality, **per-case log** |
| `raw_data_audit.py` | the original recompute | the prior `audit_report.json` |

Data: `data/exp/3provider_300.jsonl` (300 core records, 275 validated), three `…/05_label_eval.jsonl` (897 labeled outputs), nine `…/06_judge.jsonl` (2,683 verdicts). The per-LLM-call traces are browsable via `perturb viewer` (prompts/responses/parsed JSON per record/step).

**Superseded:** `archive_fpr_review/` holds an earlier FPR-focused review tool and its 34 judgements. It was replaced by the behavior×cell audit and is kept only for provenance — **do not cite its numbers**.

---

## Appendix — per-case adjudication log
See **`cell_audit_findings.md` → "Per-case adjudication log"** for every reviewed case (case_id, generator→judge, same/cross, your `gold_ok`/`judge_ok` calls, the derived verdict, notes, and the question). Regenerate with `python paper/audit/gen_audit_dossier.py` after any further labelling.
