"""Behavior-stratified judge performance: step 6 (judge verdicts) broken down by
step 5 (generator behavior label). Read-only over raw JSONL.

This is the analysis that explains the judge matrix: where recall comes from
(committed answers) and where the apparent false positives come from
(refusals / conflict-aware answers).

Foolproofing baked in:
  * Behavior label is the LLM label-evaluation output ONLY (the Table 1 source).
    Outputs with no llm_eval are reported as a separate UNLABELED row, never
    silently folded into another class.
  * Verdicts within one answer (3 judges) are NOT independent, so every headline
    rate gets a cluster bootstrap CI resampled BY ANSWER (core_id, generator).
  * Zero-event rates (e.g. memory_override FPR) report a rule-of-three upper
    bound instead of a degenerate [0, 0] bootstrap interval.

Outputs:
  paper/audit/behavior_stratified_report.json
  paper/tables/behavior_stratified.tex

Run: python paper/audit/behavior_stratified.py
"""
from __future__ import annotations

import json
import os
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
AUDIT_DIR = Path(__file__).resolve().parent
TABLES_DIR = ROOT / "paper" / "tables"

GATES = ["type_valid", "answer_causal", "global_context_consistent", "no_original_answer_leakage", "original_contradicts_perturbed"]
PROVIDERS = ["GPT", "Grok", "Gemini"]
LABEL_RUNS = {
    "GPT": "data/runs/20260531-005101-gen-gpt55-300/05_label_eval.jsonl",
    "Grok": "data/runs/20260531-005112-gen-grok-300/05_label_eval.jsonl",
    "Gemini": "data/runs/20260531-005123-gen-gemini-300/05_label_eval.jsonl",
}
JUDGE_RUNS = {
    ("GPT", "GPT"): "data/runs/20260531-175601-judge-gpt-on-gpt/06_judge.jsonl",
    ("Grok", "GPT"): "data/runs/20260531-175608-judge-grok-on-gpt/06_judge.jsonl",
    ("Gemini", "GPT"): "data/runs/20260531-175617-judge-gemini-on-gpt/06_judge.jsonl",
    ("GPT", "Grok"): "data/runs/20260531-212107-judge-gpt-on-grok/06_judge.jsonl",
    ("Grok", "Grok"): "data/runs/20260531-212359-judge-grok-on-grok/06_judge.jsonl",
    ("Gemini", "Grok"): "data/runs/20260531-212120-judge-gemini-on-grok/06_judge.jsonl",
    ("GPT", "Gemini"): "data/runs/20260531-230842-judge-gpt-on-gemini/06_judge.jsonl",
    ("Grok", "Gemini"): "data/runs/20260531-230848-judge-grok-on-gemini/06_judge.jsonl",
    ("Gemini", "Gemini"): "data/runs/20260531-230857-judge-gemini-on-gemini/06_judge.jsonl",
}
BEHAVIOR_ORDER = [
    "context_follow", "both_claims", "memory_override",
    "conflict_awareness", "refusal_or_insufficient", "unrelated_or_failed",
]
N_BOOT = int(os.environ.get("BEHAVIOR_BOOTSTRAP", "10000"))
SEED = int(os.environ.get("BEHAVIOR_SEED", "20260627"))


def rows(path):
    return [json.loads(x) for x in (ROOT / path).read_text(encoding="utf-8").splitlines() if x.strip()]


def passes(record):
    v = record.get("validation") or {}
    return all(v.get(g) is True for g in GATES)


def r1(x):
    return None if x is None else round(float(x), 1)


# --------------------------------------------------------------------------- #
# Load: behavior label (llm_eval only) + per-answer verdict outcomes
# --------------------------------------------------------------------------- #
behavior = {}
for gen, path in LABEL_RUNS.items():
    for r in rows(path):
        for o in r.get("generator_outputs") or []:
            behavior[(r["core_id"], gen, o.get("sample_id"))] = (o.get("llm_eval") or {}).get("behavior_label")

core = rows("data/exp/3provider_300.jsonl")
validated_ids = {r["core_id"] for r in core if passes(r)}

# answer key -> {"beh", "verdicts": [(gold, pred, is_matching)]}
answers = defaultdict(lambda: {"beh": None, "verdicts": []})
for (judge, gen), path in JUDGE_RUNS.items():
    for r in rows(path):
        if r["core_id"] not in validated_ids:
            continue
        for v in r.get("judge_verdicts") or []:
            key = (r["core_id"], gen, v.get("generator_sample_id"))
            answers[key]["beh"] = behavior.get(key)
            answers[key]["verdicts"].append(
                (bool(v.get("gold_has_induced_error")), bool(v.get("contains_factual_error")), judge == gen)
            )

by_beh = defaultdict(list)
for key, a in answers.items():
    by_beh[a["beh"] if a["beh"] else "UNLABELED"].append(a)

rng = np.random.default_rng(SEED)


def cluster_ci(answer_lists):
    """answer_lists: list (per answer) of 0/1 preds among the relevant verdicts.
    Cluster bootstrap by answer. Returns point, lo, hi (percentages)."""
    items = [np.array(a, dtype=float) for a in answer_lists if len(a)]
    if not items:
        return None
    flat_num = sum(a.sum() for a in items)
    flat_den = sum(a.size for a in items)
    point = 100 * flat_num / flat_den
    n = len(items)
    sums = np.array([a.sum() for a in items])
    cnts = np.array([a.size for a in items], dtype=float)
    W = rng.multinomial(n, np.full(n, 1.0 / n), size=N_BOOT).astype(np.float64)
    numer = W @ sums
    denom = W @ cnts
    ok = denom > 0
    reps = 100 * numer[ok] / denom[ok]
    lo, hi = np.percentile(reps, [2.5, 97.5])
    # zero-event: bootstrap collapses to [0,0]; use rule of three (3/n_verdicts).
    if flat_num == 0:
        hi = 100 * 3.0 / flat_den
        note = "rule-of-three upper bound (0 events)"
    elif flat_num == flat_den:
        lo = 100 * (1 - 3.0 / flat_den)
        note = "rule-of-three lower bound (all events)"
    else:
        note = None
    return {"point": r1(point), "ci_low": r1(lo), "ci_high": r1(hi), "note": note}


def block(answer_list):
    nv = sum(len(a["verdicts"]) for a in answer_list)
    na = len(answer_list)
    tp = fp = fn = tn = goldpos = same_flag = same_n = cross_flag = cross_n = 0
    for a in answer_list:
        for gold, pred, same in a["verdicts"]:
            goldpos += gold
            if gold and pred:
                tp += 1
            elif gold and not pred:
                fn += 1
            elif (not gold) and pred:
                fp += 1
            else:
                tn += 1
            if same:
                same_n += 1; same_flag += pred
            else:
                cross_n += 1; cross_flag += pred
    is_recall = goldpos >= 0.5 * nv if nv else False
    want = is_recall  # recall -> gold-positive verdicts; FPR -> gold-negative
    per_answer = [[int(p) for g, p, _ in a["verdicts"] if g == want] for a in answer_list]
    ci = cluster_ci(per_answer)
    return {
        "n_verdicts": nv,
        "n_answers": na,
        "gold_pos_pct": r1(100 * goldpos / nv) if nv else None,
        "flag_pct": r1(100 * (tp + fp) / nv) if nv else None,
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "headline_metric": "recall" if is_recall else "fpr",
        "headline": ci,
        "same_flag_pct": r1(100 * same_flag / same_n) if same_n else None,
        "cross_flag_pct": r1(100 * cross_flag / cross_n) if cross_n else None,
    }


report = {
    "meta": {
        "description": "Step 6 (judge verdicts) stratified by step 5 (generator behavior label).",
        "set": "validated records only",
        "behavior_source": "LLM label-evaluation (llm_eval) ONLY; outputs without llm_eval are reported as UNLABELED",
        "ci": "cluster bootstrap by answer (core_id, generator)",
        "bootstrap": {"replicates": N_BOOT, "seed": SEED},
        "headline_rule": "recall when >=50% of verdicts are gold-positive, else false-positive rate; recall/FPR computed on the relevant gold subset",
        "note": "Verdicts are pooled across all 9 judge cells (same- and cross-deployment); same/cross flag rates given per behavior.",
    },
    "behaviors": {},
}
order = BEHAVIOR_ORDER + [b for b in by_beh if b not in BEHAVIOR_ORDER]
tot = dict(tp=0, fp=0, fn=0, tn=0, n=0)
for b in order:
    if b not in by_beh:
        continue
    blk = block(by_beh[b])
    report["behaviors"][b] = blk
    for k in ("tp", "fp", "fn", "tn"):
        tot[k] += blk[k]
    tot["n"] += blk["n_verdicts"]
report["totals"] = tot

(AUDIT_DIR / "behavior_stratified_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


# --------------------------------------------------------------------------- #
# LaTeX
# --------------------------------------------------------------------------- #
PRETTY = {
    "context_follow": "context-follow (adopts false value)",
    "both_claims": "both-claims (true + false value)",
    "memory_override": "memory-override (uses true value)",
    "conflict_awareness": "conflict-aware (notices source is off)",
    "refusal_or_insufficient": "refusal / insufficient",
    "unrelated_or_failed": "unrelated / failed",
    "UNLABELED": "unlabeled (no llm\\_eval)",
}


def tex():
    L = ["% Auto-generated by paper/audit/behavior_stratified.py -- do not edit by hand.",
         r"\begin{table*}[t]", r"\centering", r"\small",
         r"\begin{tabular}{l rr rrrr l}", r"\toprule",
         r"Generator behavior (step 5) & verdicts & answers & TP & FP & FN & TN & Headline rate [95\% CI] \\",
         r"\midrule"]
    for b in order:
        if b not in report["behaviors"]:
            continue
        x = report["behaviors"][b]
        h = x["headline"]
        rate = x["headline_metric"].upper().replace("FPR", "FPR").replace("RECALL", "recall")
        ci = "--" if not h else f"{rate} {h['point']:.1f} [{h['ci_low']:.1f}, {h['ci_high']:.1f}]"
        sep = r"\midrule" if b == "UNLABELED" else ""
        if sep:
            L.append(sep)
        L.append(f"{PRETTY.get(b, b)} & {x['n_verdicts']} & {x['n_answers']} & {x['tp']} & {x['fp']} & {x['fn']} & {x['tn']} & {ci} \\\\")
    L.append(r"\bottomrule")
    L.append(r"\end{tabular}")
    L.append(
        r"\caption{Judge outcomes (step 6) stratified by generator behavior (step 5), validated records, "
        r"pooled over all nine judge cells. TP/FP/FN/TN are true/false positives/negatives against the induced-error "
        r"gold. The headline rate is recall for committed answers and false-positive rate (FPR) otherwise, with a "
        r"95\% cluster bootstrap CI resampled by answer (" + f"{N_BOOT:,}" + r" replicates). "
        r"Recall is concentrated in context-follow answers; false positives are concentrated in conflict-aware and "
        r"refusal answers, while memory-override controls are essentially never flagged. Behavior labels are the "
        r"LLM label-evaluation output; the three outputs without a label are shown separately as unlabeled.}"
    )
    L.append(r"\label{tab:behavior-stratified}")
    L.append(r"\end{table*}")
    return "\n".join(L) + "\n"


TABLES_DIR.mkdir(parents=True, exist_ok=True)
(TABLES_DIR / "behavior_stratified.tex").write_text(tex(), encoding="utf-8")

# --------------------------------------------------------------------------- #
# Asserts + console
# --------------------------------------------------------------------------- #
assert tot["tp"] + tot["fp"] + tot["fn"] + tot["tn"] == tot["n"], "confusion cells do not reconcile"
print(f"validated verdicts={tot['n']}  TP={tot['tp']} FP={tot['fp']} FN={tot['fn']} TN={tot['tn']}")
print(f"{'behavior':26s}{'verds':>6}{'ans':>5}{'gold+%':>8}  headline [95% CI]")
for b in order:
    if b not in report["behaviors"]:
        continue
    x = report["behaviors"][b]; h = x["headline"]
    s = f"{x['headline_metric']}={h['point']:.1f}% [{h['ci_low']:.1f}, {h['ci_high']:.1f}]" if h else "--"
    extra = f"  ({h['note']})" if h and h.get("note") else ""
    print(f"{b:26s}{x['n_verdicts']:>6}{x['n_answers']:>5}{x['gold_pos_pct']:>8}  {s}{extra}")
print("Wrote behavior_stratified_report.json + ../tables/behavior_stratified.tex")
