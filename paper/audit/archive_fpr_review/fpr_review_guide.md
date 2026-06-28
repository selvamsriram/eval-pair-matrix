# FPR / Target-Negative Audit — Reviewer Guide

**This is a *targeted author audit* (manual adjudication sample), not independent human annotation.** Use this exact wording in the paper unless ≥2 independent annotators review the cases.

## Why you are doing this

The paired analysis (Agent 1) found a robust result: **same-deployment judges flag *target-negative* answers less often** than cross-deployment judges. But "target-negative" only means the answer did **not** express the *planted* perturbation. The judge prompt asks about **any** factual error against the original passages. So some apparent false positives may be **legitimate alternate errors** the judge correctly caught.

Your job: for a focused, prioritized sample, decide whether each flag is a **real false alarm** or an **alternate valid error** — and whether each miss is a real miss. This determines how strongly the paper can word the FPR result.

## The one distinction that matters

| Evaluation | Question | Alternate errors count? |
|---|---|---|
| **Target-error** | Did the judge catch the *planted* perturbation? | No |
| **Any-error** | Did the judge catch *any* real source-grounding problem? | Yes |

The paper currently mixes these. You are untangling them.

## Ground rules

- **Judge only against the provided original passages.** Do **not** use outside knowledge. If the original passages support a claim, it is correct *for our purposes*, even if you personally know otherwise.
- The **original passage is the reference.** The generator answered from a *perturbed* source; the planted change is shown to you (original span → perturbed span) only so you can tell whether the answer repeats the perturbation.
- **Do not relabel all 2,683 verdicts.** Only the queue.
- **Do not rewrite the scientific claim** while reviewing.
- **Ambiguous cases stay ambiguous** — use `unclear`, don't force a call.

## What each case shows you

- The **question** and the generator's **full answer**.
- The **planted change**: `original_value → perturbed_value`, the original vs perturbed atomic claim, and the exact edited span in the modified passage(s).
- The **judge's verdict**: whether it flagged an error, its `wrong_claim`, its explanation, and the source passage it cited.
- **Auto-hints** (machine guesses, *not* answers):
  - `auto_target_match` — does the judge's wrong_claim text contain the perturbed value? (rough "did it name the target?")
  - `auto_localization_match` — is the cited passage one of the modified passages?
- The **cited passage text** and the **full original passages** (collapsible) so you can verify alternate errors and localization.

## The six fields you fill

### 1. `human_target_present` — does the answer assert the *perturbed* claim?
Compare the answer to `original_value` (e.g. 48%) vs `perturbed_value` (e.g. 35%).
- Answer says the perturbed value (35%) → **yes**
- Answer avoids both → **no**
- Answer states **both** → **yes**, and write `both claims` in notes
- Genuinely can't tell → **unclear**

### 2. `human_judge_detected_target` — did the judge identify the *planted* error?
Look at the judge's `wrong_claim` + explanation.
- Judge says "answer wrongly says 35%, source says 48%" → **yes**
- Judge flagged a *different* issue → **no**
- Judge didn't flag anything (gold-negative / false-negative cases) → **n/a**

### 3. `human_alternate_valid_error` — did the judge catch a *different real* error? **(the key field)**
Only relevant when the target is absent but the judge still flagged something.
- Answer has another claim that is unsupported/contradicted by the **original** passages, and the judge correctly catches it → **yes**
- The judge's complaint is not actually supported by the passages → **no**
- Can't tell → **unclear**

### 4. `human_false_alarm` — was the judge actually *wrong* to flag?
Decide this **after** fields 2 and 3.
- **yes** = answer had no target error **and** no other valid error — the judge was wrong.
- **no** = the judge found the target error *or* a real alternate error.
- Not a flagged case (TN / FN) → **n/a**

### 5. `human_localization_correct` — did the judge cite the right passage?
- Target errors → cited passage should be one of the original passages behind the modified passage IDs.
- Alternate errors → cited passage should be the one that actually supports your judgment.
- No flag / not applicable → **n/a**

### 6. `human_notes` — free text
Anything notable: `both claims`, `refusal`, `partial`, "judge right but cited wrong passage", etc.

## Decision tree (apparent false positives — the priority cases)

```
Is the perturbed claim asserted in the answer?  ──yes──▶ target_present=yes; this is really a (mislabeled) target case, note it
        │ no
        ▼
Did the judge flag a claim that the ORIGINAL passages contradict / do not support?
        │
   ┌────┴─────┐
  yes         no
   │           │
   ▼           ▼
alternate_valid_error=yes      false_alarm=yes
false_alarm=no                 alternate_valid_error=no
(judge was right, wrong label) (judge was genuinely wrong)
```

## Worked example (already-filled illustration)

> **Question:** How did Caitlin Clark's WNBA debut influence league attendance in 2024?
> **Planted change:** `48%` → `35%` (passage 1: "league saw a **48%** jump" → "**35%** jump").
> **Answer:** "...leaguewide attendance rose **35%** from 2023, reaching 2,353,735 fans..."
> **Judge:** flagged error; wrong_claim = "attendance rose 35%..."; cited passage 1; "source says 48%, not 35%."

Filled labels:
```
human_target_present        = yes      (answer states 35%, the perturbed value)
human_judge_detected_target = yes      (judge named 35% vs 48%)
human_alternate_valid_error = n/a      (target was present)
human_false_alarm           = no       (judge correctly caught the target)
human_localization_correct  = yes      (cited passage 1, a modified passage)
human_notes                 = clean true-positive sanity case
```

## Priorities (the queue is pre-ordered)

1. **Same-deployment apparent FPs** (all) — directly affect the result.
2. **Cross-deployment apparent FPs** (matched sample) — tells us if cross judges flag more because they catch more real alternate errors.
3. **Paper examples** — every example shown in the paper must be verified (incl. the Table 7 ASC 842 / FASB / SEC case).
4. **False negatives** (30) — are missed target errors real misses, or was the gold too aggressive?
5. **Sanity TP/TN** (15 + 15) — checks the instructions and existing labels are sane.

## What your counts will produce

The summary tallies, per subset, how many flags were **target errors / alternate valid errors / false alarms / unclear**, and which conclusion the data supports:

- **Case A** — most apparent FPs are real false alarms → strong result ("fewer false alarms on own generator").
- **Case B** — many are alternate valid errors but same/cross rates are similar → note the caveat, claim survives.
- **Case C** — cross judges flag more because they catch more alternate errors → soften to a "target-negative flag-rate difference"; becomes a methodological contribution.

Fill the queue in the dashboard (`python paper/audit/fpr_review_app.py`); your labels auto-save and the summary updates live.
