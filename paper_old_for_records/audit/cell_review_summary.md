# Behavior x cell review summary

_Targeted author audit. Each case: is the gold label right (gold_ok) and did the judge call it right vs the source (judge_ok)._

Progress: **88 / 153** cases reviewed.

| Behavior | Cell | sampled / pop | reviewed | gold ok (y/n/?) | judge ok (y/n/?) | cell valid |
|---|---|---|---|---|---|---|
| context_follow | TP | 12/1025 | 8 | 8/0/0 | 7/1/0 | 7 |
| context_follow | FN | 12/187 | 9 | 6/3/0 | 3/6/0 | 0 |
| both_claims | TP | 12/88 | 0 | 0/0/0 | 0/0/0 | 0 |
| both_claims | FN | 12/44 | 0 | 0/0/0 | 0/0/0 | 0 |
| both_claims | TN | 3/3 | 0 | 0/0/0 | 0/0/0 | 0 |
| memory_override | TN | 12/42 | 10 | 10/0/0 | 10/0/0 | 10 |
| conflict_awareness | TP | 3/3 | 3 | 3/0/0 | 3/0/0 | 3 |
| conflict_awareness | FP | 12/46 | 7 | 6/0/1 | 7/0/0 | 6 |
| conflict_awareness | TN | 5/5 | 0 | 0/0/0 | 0/0/0 | 0 |
| refusal_or_insufficient | TP | 12/23 | 12 | 11/1/0 | 12/0/0 | 11 |
| refusal_or_insufficient | FP | 12/130 | 8 | 6/2/0 | 8/0/0 | 6 |
| refusal_or_insufficient | FN | 1/1 | 0 | 0/0/0 | 0/0/0 | 0 |
| refusal_or_insufficient | TN | 12/246 | 10 | 10/0/0 | 10/0/0 | 10 |
| unrelated_or_failed | FP | 12/25 | 10 | 10/0/0 | 10/0/0 | 10 |
| unrelated_or_failed | TN | 12/581 | 11 | 11/0/0 | 11/0/0 | 11 |
| UNLABELED | FP | 8/8 | 0 | 0/0/0 | 0/0/0 | 0 |
| UNLABELED | TN | 1/1 | 0 | 0/0/0 | 0/0/0 | 0 |

**cell valid** = gold_ok yes AND judge_ok yes (the verdict is correctly placed in this cell). Derivations: FP with judge_ok=yes -> alternate/real error the target-gold missed; FP with judge_ok=no -> genuine false alarm; FP/FN with gold_ok=no -> gold mislabel; TN with judge_ok=no -> judge missed a real error.
