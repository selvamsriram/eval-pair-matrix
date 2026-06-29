# Statistical Rescue of the Eval-Pair-Matrix Paper — Work Memo

**Prepared for:** research-group discussion
**Date:** 2026-06-27
**Scope:** Response to Round-1 review item *"Statistical rescue agent"* — fixing the same-model confound using existing data only.
**Artifacts:** `paper/audit/paired_audit.py` (+ JSON report, summary, CSV) and `paper/tables/{validated_matrix,paired_effects}.tex`.

---

## 0. TL;DR

- The reviewer's central objection is **correct**: our headline same-model-bias number compared a judge against *itself on different answers*, so it conflated bias with generator difficulty.
- We rebuilt the analysis as a **paired, within-answer** comparison (every answer was judged by all three judges) and attached **cluster-bootstrap confidence intervals** (resampled by question).
- **Result, on the 275 validated records:**
  - **No robust same-deployment effect on recall** (Δ = −0.5 pp, 95% CI [−2.7, +1.7]). The old "−6.2-pt GPT self-leniency" was a confound and **does not survive**.
  - **A robust same-deployment effect on false positives** (FPR Δ = −4.3 pp, CI [−6.6, −2.0]) and overall flag rate (Δ = −2.2 pp, CI [−3.8, −0.6]). A judge **over-flags its own model's *correct* answers less often**.
- Net: the paper's claim must be **reframed**, but the reframing is *stronger and more defensible* — and is exactly the kind of controlled/negative result GroundLM solicits.
- The whole thing is reproducible from one read-only script and was double-checked with two independent recomputations.

---

## 1. Background and the reviewer's objection

The experiment is a fully-crossed **3×3 judge × generator matrix**. Three generators (GPT, Grok, Gemini) answer questions whose source passages carry a deliberately planted ("induced") error; three judges (GPT, Grok, Gemini) each decide whether each answer contains a factual error.

The original paper measured **same-model bias** by a **diagonal-vs-off-diagonal** contrast: e.g. GPT-judge on GPT answers (diagonal) vs GPT-judge on Grok/Gemini answers (off-diagonal). The reviewer's objection:

> Those off-diagonal cells are **different answers** with different length, style, refusal rate, and difficulty. A lower diagonal score can be difficulty, not bias.

The reviewer's smoking gun from our own matrix: on GPT's answers, GPT-judge recall = 77.5% and **Grok-judge recall = 77.7%** — essentially identical. If GPT-judge were uniquely lenient toward GPT answers, an outside judge would not miss the same errors. So the claimed −6.2-pt "GPT self-leniency" was an artifact of comparing across answer columns of unequal difficulty.

**Conclusion:** the fix is not "add error bars to the existing contrast"; the contrast itself does not identify the effect. We need a paired, answer-level estimator.

---

## 2. Reframed research question (estimand)

We replace:

> *Does a judge perform differently on its own model's outputs than on other generators' outputs?* (confounded)

with:

> **On the exact same candidate answer, does the matching judge behave differently from the non-matching judges?** (paired, difficulty-controlled)

Terminology: we call this the **same-deployment pairing effect** (not "same-model-family bias"), because the design has exactly one deployment per provider and no same-provider/different-model condition — it cannot separate exact-model, provider-family, and style-familiarity effects.

---

## 3. Data and integrity checks (done before any analysis)

| Check | Finding |
|---|---|
| Unit of analysis | An "answer" = `(core_id, generator)`; `generator_sample_id` is always 0. **896** unique answers. |
| Full crossing | **891/896** answers have all 3 judges; 5 have only 2 (missing verdicts). |
| Usable for pairing | **894** answers have the matching judge + ≥1 non-matching judge (2 dropped). |
| Gold stability | `gold_has_induced_error` is identical across the 3 judges for **every** answer (0 inconsistencies). |
| Field semantics | `verdict ∈ {incorrect, correct}` maps 1:1 to boolean `contains_factual_error`; used as the prediction. |
| Provider/model IDs | `azure-gpt`→GPT (`gpt-5.4`), `grok`→Grok (`grok-4.3`), `gemini`→Gemini (`gemini-3.5-flash`). |
| Totals (asserted) | 300 core records, **275 validated** / 25 gap-fill, **2,683** verdicts. |

These were verified directly against the raw JSONL; the script `assert`s the totals so it fails loudly on data drift.

---

## 4. Methodology

### 4.1 Flatten everything
All **2,683 verdicts** flattened to one long table (`paired_verdicts.csv`): one row per verdict with `core_id`, `is_validated`, generator/judge provider+model, `pair_type`, gold, prediction, `wrong_claim`, cited passage, modified passages, `perturbation_type`, and the generator's `behavior_label` (joined from the label-eval files). This is the single source of truth for all downstream computation and is hand-auditable.

### 4.2 Validated-only is primary
Only **275/300** records pass all five validation gates. Per the review, we make the **275 validated records the primary benchmark**, the **300 full set** a sensitivity check, and the **25 gap-fill** records a separate diagnostic. Every analysis is produced for all three sets.

### 4.3 Descriptive confusion matrices
For each set we build the 3×3 matrix with per-cell TP/FP/FN/TN, precision, recall, F1, FPR. **Descriptive only** — not the inferential claim. (See §5.1: the validated matrix is essentially flat on the diagonal.)

### 4.4 The paired delta (the core estimand)
For each usable answer:

```
same_pred   = matching judge's prediction        (0/1)
cross_mean  = mean of the two non-matching judges (0, 0.5, 1)
delta       = same_pred − cross_mean
```

`delta` = "on this one answer, did the same-deployment judge flag it more (+) or less (−) than outsiders?" Averaged over answer slices:

- **gold-positive** answers → **recall Δ** (does it miss its own model's *real* errors?)
- **gold-negative** answers → **FPR Δ** (does it over-flag its own model's *correct* answers?)
- **all** answers → **flag-rate Δ**

Because each delta is within a single answer, **answer difficulty cancels** — the confound is removed by construction. We also retain the old confounded diagonal-minus-off-diagonal numbers side-by-side for contrast.

### 4.5 Cluster bootstrap for confidence intervals
Two design points (both raised and resolved during review):

1. **Resample questions, not answers.** A question's ≤3 answers share source passages, planted error, and difficulty — they are correlated, not independent. Resampling the 894 answers i.i.d. would fake ~894 independent units (really ~300) and produce intervals that are **too narrow**. We instead **cluster-bootstrap by `core_id`**: resample whole questions with replacement, carrying all their answers as a block.
2. **Resample each dataset's own cluster population.** The validated benchmark is a sample of the **275** validated questions, so its CI resamples **275** questions (not all 300). Full resamples 300; gap-fill resamples 25. (Resampling 300 for a validated-only estimand injects extra variance from a fluctuating validated count that isn't part of that estimand.)

Implementation: 10,000 multinomial weight-vectors per dataset; per-question sufficient statistics; replicate means via matrix multiplication (ratio estimator, varying denominator); **95% percentile** intervals. Seeded and reproducible.

---

## 5. Results

### 5.1 The raw matrix is already flat (confirms the objection)
Validated-only 3×3 (P/R/F1 per cell; **diagonal bold**):

| Judge \ Gen | GPT | Grok | Gemini | Row F1 |
|---|---|---|---|---|
| **GPT** | **94.0/78.1/85.3** | 77.9/81.6/79.7 | 81.6/83.2/82.4 | 82.5 |
| **Grok** | 90.0/77.8/83.4 | **80.1/79.6/79.9** | 85.8/85.8/85.8 | 83.0 |
| **Gemini** | 89.2/86.4/87.8 | 78.1/85.0/81.4 | **85.4/90.6/87.9** | 85.7 |

Mean diagonal F1 = **84.4** vs off-diagonal **83.4** → a **0.9-pt** gap. The raw same-model signal was never large; it only *looked* large when sliced the confounded way.

### 5.2 Headline paired effects (275 validated, 95% CI)

| Contrast | same % | cross % | Δ (pp) | 95% CI | Robust? |
|---|---|---|---|---|---|
| Recall (gold-positive) | 82.7 | 83.2 | **−0.5** | [−2.7, +1.7] | **No** (includes 0) |
| FPR (gold-negative) | 16.5 | 20.8 | **−4.3** | [−6.6, −2.0] | **Yes** |
| Flag-rate (all) | 53.4 | 55.6 | **−2.2** | [−3.8, −0.6] | **Yes** |

Two-part finding:
1. **Recall null** — controlling for difficulty, a judge is **not** worse at catching its own model's genuine errors. The original self-leniency-as-missed-errors claim **fails**.
2. **FPR / flag-rate effect** — a judge is ~4 pts **less likely to wrongly flag its own model's correct answers**. Same-deployment leniency surfaces as **reduced over-flagging**, not missed errors.

### 5.3 Per-generator (EXPLORATORY, uncorrected for multiple testing)

| Generator | paired recall Δ | 95% CI | crosses 0? | old unpaired Δ |
|---|---|---|---|---|
| GPT-on-GPT | −3.8 | [−8.0, +0.3] | yes | −4.3 |
| Grok-on-Grok | −3.7 | [−8.7, +0.7] | yes | −2.2 |
| Gemini-on-Gemini | **+6.0** | [+2.9, +9.6] | **no** | +4.9 |

GPT and Grok recall deltas now straddle zero; only Gemini survives and it is the **opposite sign** (more self-skeptical). The "three provider personalities that conveniently cancel" narrative does not hold up.

### 5.4 Sensitivity (global paired deltas)

| Set | recall Δ | FPR Δ | flag-rate Δ | n answers |
|---|---|---|---|---|
| Validated (275) | −0.5 [−2.7, +1.7] | −4.3 [−6.6, −2.0] | −2.2 [−3.8, −0.6] | 819 |
| Full (300) | −0.7 [−2.8, +1.4] | −4.2 [−6.3, −2.1] | −2.2 [−3.8, −0.7] | 894 |
| Gap-fill (25) | −2.4 [−8.8, +2.6] | −2.9 [−6.9, +0.0] | −2.7 [−6.7, +0.7] | 75 |

The validated and full sets agree; gap-fill is underpowered (as expected at n=25).

---

## 6. What this means for the paper

- **The headline must change**, but for the better. Proposed framing:
  > Across a fully crossed 3×3 matrix, raw diagonal differences are small (mean diagonal F1 84.4 vs off-diagonal 83.4). After a paired, answer-level analysis on 275 validated records, there is **no robust same-deployment effect on recall** (Δ = −0.5 pp, CI [−2.7, +1.7]), but a **robust same-deployment leniency on gold-negative answers** (FPR Δ = −4.3 pp, CI [−6.6, −2.0]); generator behaviour and answerability explain most of the matrix variation.
- **General methodological takeaway** (a real contribution): *full matrices are useful, but raw diagonal-vs-off-diagonal comparisons can mislead unless generator difficulty and answer-level pairing are controlled.* This is more defensible and more broadly useful than three provider "personalities."
- **A null/small controlled effect is publishable at GroundLM** — the workshop explicitly welcomes negative results.

---

## 7. Deliverables

| File | What it is |
|---|---|
| `paper/audit/paired_audit.py` | Read-only analysis script (paths anchored to file; runs anywhere) |
| `paper/audit/paired_audit_report.json` | Full machine-readable results + provenance |
| `paper/audit/paired_audit_summary.md` | Human-readable headline, decision rule, draft abstract sentence |
| `paper/audit/paired_verdicts.csv` | Flattened 2,683-row verdict table |
| `paper/tables/validated_matrix.tex` | Paper-ready validated 3×3 matrix |
| `paper/tables/paired_effects.tex` | Paper-ready paired effects with CIs |

Read-only confirmed: nothing under `data/` is modified.

---

## 8. Verification & robustness

- **Independent recompute #1:** all three point estimates + a bootstrap CI re-derived from scratch (separate code, separate seed) → matched (recall −0.548, FPR −4.27, flag −2.20).
- **Independent recompute #2:** after switching to 275-core resampling, validated CIs re-checked by resampling exactly the 275 validated cores with a third seed → matched to Monte-Carlo noise.
- **Seed stability:** CIs move < 0.1 pp across seeds at 10,000 replicates.
- **Hard asserts** on 300 / 275 / 2,683 guard against silent data drift.

---

## 9. Limitations of *this* analysis (be explicit in the paper)

- The CI captures sampling variability from the **finite question set only**. It does **not** capture: judge run-to-run randomness (single-shot, fixed temperature), noise in the **LLM-generated gold/behavior labels**, or model/prompt sensitivity.
- The gold label is "answer expresses the *induced* perturbation," but the judge prompt asks about "*any* factual error." This **target-vs-any-error mismatch** is unresolved here (it is a separate review item — see §10) and means some "false positives" may be genuine alternate errors.
- The estimator cannot separate exact-model vs provider-family vs style-familiarity effects (one deployment per provider).

---

## 10. Open decisions & proposed next steps (for the group)

The review listed 9 steps; **we have completed the statistical core (Steps 2 & 4)**. Remaining items, with a suggested priority for discussion:

**A. Strategic framing decision (discuss first).**
Do we commit to the reframed headline — *"no same-deployment recall effect; a real false-positive leniency; generator behaviour dominates"* — as the paper's thesis? Everything else depends on this.

**B. High-priority, still needed for a credible archival submission (review Steps 3, 5):**
1. **Target-aware scoring (Step 3).** Separate `judge_target_detected` (found the induced error) from `alternate_error_detected` (found a different real error). This decides whether the FPR effect is "leniency" or "different real errors." *Likely the most important remaining analysis.*
2. **Focused human audit (Step 5).** Even a modest audit (all 25 failed records + ~75 validated + ~90 candidate answers, 2 annotators on ≥50 overlap, report κ/α) materially raises reviewer confidence, since gold + behavior labels are currently LLM-generated.

**C. Explanatory analyses, mostly from existing data (review Step 6):**
3. **Behavior-stratified judge performance** (context-follow / both-claims / conflict-aware / refusal / unrelated) — directly show that the Grok column is hard because of refusals/hedging, rather than asserting it.
4. **Demote/condition generator-side "self-affinity"** (Step 6B): perturber identity is confounded with perturbation type.
5. **Localization metrics** (Step 6C): joint localized recall, chance baseline, de-cited subset.
6. **Cheap baselines** (Step 6D): deterministic target matcher, majority vote, cross-judge ensemble, optional NLI — establish that the expensive pipeline beats simple alternatives.

**D. Writing & packaging (review Steps 1, 7, 8, 9):**
7. Rewrite abstract/contributions/results/discussion around the controlled result; add exact model/inference table.
8. Related work: **Chen et al. 2025** (no overarching self-preference in fact-centric RAG — closest prior work), ContextualJudgeBench, REFLECT, RAGferee; update GaRAGe to the Findings-of-ACL version.
9. Page-limit / float / anonymity fixes.

**E. Optional methodological extensions (only if we want extra rigor):**
- A permutation/sign-flip test of the same-vs-cross label as a complementary p-value.
- A mixed-effects model (`detected ~ judge + generator + same_deployment + (1|question) + (1|answer)`) as a parametric cross-check of the bootstrap.

**Deadline context:** GroundLM direct-submission deadline is **June 29, 2026 AoE** (8 content pages, archival long paper). Given the deadline, the realistic minimum viable set is **A → B(1) → D(7,8)**; B(2) and C strengthen it if time permits.

---

## Appendix — Reproduce

```bash
python paper/audit/paired_audit.py
# optional: PAIRED_BOOTSTRAP=10000 PAIRED_SEED=20260627 python paper/audit/paired_audit.py
```
Reads only JSONL under `data/`; writes the six artifacts in §7.
