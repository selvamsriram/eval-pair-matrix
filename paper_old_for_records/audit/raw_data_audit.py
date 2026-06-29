"""Recompute the paper's central numbers from raw JSONL data.

Run from the repository root:
    python audit/raw_data_audit.py

This script intentionally reads JSONL artifacts under data/ and does not read
repository markdown summaries.
"""
import json
import re
from pathlib import Path
from collections import Counter, defaultdict

ROOT = Path.cwd()
GATES = ["type_valid", "answer_causal", "global_context_consistent", "no_original_answer_leakage", "original_contradicts_perturbed"]
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

def rows(path):
    return [json.loads(x) for x in (ROOT / path).read_text(encoding="utf-8").splitlines() if x.strip()]

def passes(record):
    v = record.get("validation") or {}
    return all(v.get(gate) is True for gate in GATES)

def pct(n, d):
    return None if not d else round(100 * n / d, 3)

def prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 0
    r = tp / (tp + fn) if tp + fn else 0
    f = 2 * p * r / (p + r) if p + r else 0
    return round(100 * p, 3), round(100 * r, 3), round(100 * f, 3)

_norm_re = re.compile(r"[\s\W_]+")
def norm(s):
    return _norm_re.sub(" ", (s or "").lower()).strip()

report = {"files": {}}
core = rows("data/exp/3provider_300.jsonl")
report["files"]["data/exp/3provider_300.jsonl"] = len(core)
pc, tc, fail = Counter(), Counter(), Counter()
valid = 0
for record in core:
    pc[((record.get("generators") or {}).get("perturb") or {}).get("provider", "unknown")] += 1
    tc[record.get("perturbation_type") or "unknown"] += 1
    if passes(record):
        valid += 1
    else:
        v = record.get("validation") or {}
        for gate in GATES:
            if v.get(gate) is not True:
                fail[gate] += 1
report["core"] = {
    "n": len(core),
    "unique_core_ids": len({r.get("core_id") for r in core}),
    "validated": valid,
    "gap_fill": len(core) - valid,
    "providers": dict(pc),
    "types": dict(tc),
    "gap_fail_gates": dict(fail),
}

gen_summary, self_affinity, val_gap, type_push = {}, {}, {}, {}
total_outputs = total_eval = 0
for gen, path in LABEL_RUNS.items():
    run_rows = rows(path)
    report["files"][path] = len(run_rows)
    labels = Counter()
    outputs = evals = own_total = own_cf = other_total = other_cf = 0
    valid_total = valid_cf = gap_total = gap_cf = 0
    self_refusals = llm_refusals = cf_den = cf_cite = 0
    by_type = defaultdict(Counter)
    for record in run_rows:
        perturber = ((record.get("generators") or {}).get("perturb") or {}).get("provider", "unknown")
        modified = set(record.get("modified_passage_ids") or [])
        is_valid = passes(record)
        ptype = record.get("perturbation_type") or "unknown"
        for out in record.get("generator_outputs") or []:
            outputs += 1
            ev = out.get("llm_eval")
            if not ev:
                continue
            evals += 1
            label = ev.get("behavior_label") or "missing"
            labels[label] += 1
            if out.get("is_refusal"):
                self_refusals += 1
            if label == "refusal_or_insufficient":
                llm_refusals += 1
            cf = label == "context_follow"
            if out.get("generator_provider") == perturber:
                own_total += 1; own_cf += cf
            else:
                other_total += 1; other_cf += cf
            if is_valid:
                valid_total += 1; valid_cf += cf
            else:
                gap_total += 1; gap_cf += cf
            if cf:
                cf_den += 1; cf_cite += bool(set(out.get("cited_passage_ids") or []) & modified)
            by_type[ptype]["n"] += 1
            by_type[ptype]["cf"] += cf
            by_type[ptype]["mem"] += label == "memory_override"
            by_type[ptype]["conf"] += label == "conflict_awareness"
    total_outputs += outputs; total_eval += evals
    gen_summary[gen] = {"outputs": outputs, "llm_eval": evals, "labels": dict(labels), "rates": {k: pct(v, evals) for k, v in labels.items()}, "self_declared_refusals": self_refusals, "llm_refusals": llm_refusals, "cf_cited_modified": [cf_cite, cf_den, pct(cf_cite, cf_den)]}
    self_affinity[gen] = {"own": [own_cf, own_total, pct(own_cf, own_total)], "others": [other_cf, other_total, pct(other_cf, other_total)], "delta_pp": round((pct(own_cf, own_total) or 0) - (pct(other_cf, other_total) or 0), 3)}
    val_gap[gen] = {"validated": [valid_cf, valid_total, pct(valid_cf, valid_total)], "gap": [gap_cf, gap_total, pct(gap_cf, gap_total)], "delta_pp": round((pct(valid_cf, valid_total) or 0) - (pct(gap_cf, gap_total) or 0), 3)}
    type_push[gen] = {t: {"n": c["n"], "mem_pct": pct(c["mem"], c["n"]), "conf_pct": pct(c["conf"], c["n"]), "cf_pct": pct(c["cf"], c["n"])} for t, c in by_type.items()}
report["generator"] = {"total_outputs": total_outputs, "total_llm_eval": total_eval, "summary": gen_summary, "self_affinity": self_affinity, "validated_vs_gap": val_gap, "type_pushback": type_push}

cells, pairs = {}, Counter()
total_verdicts = 0
for (judge, gen), path in JUDGE_RUNS.items():
    run_rows = rows(path)
    report["files"][path] = len(run_rows)
    tp = fp = tn = fn = n = gold_pos = 0
    wc_num = wc_den = cite_num = cite_den = 0
    for record in run_rows:
        modified = set(record.get("modified_passage_ids") or [])
        for verdict in record.get("judge_verdicts") or []:
            n += 1; total_verdicts += 1; pairs[verdict.get("pair_type", "missing")] += 1
            gold = bool(verdict.get("gold_has_induced_error"))
            pred = bool(verdict.get("contains_factual_error"))
            gold_pos += gold
            if gold and pred:
                tp += 1
                replacement = verdict.get("gold_perturbation_replacement") or ""
                wrong_claim = verdict.get("wrong_claim") or ""
                if replacement and wrong_claim:
                    wc_den += 1; wc_num += norm(replacement) in norm(wrong_claim)
                sid = verdict.get("supporting_source_passage_id")
                if sid is not None:
                    cite_den += 1
                    try: sid = int(sid)
                    except Exception: sid = None
                    cite_num += sid in modified
            elif (not gold) and pred:
                fp += 1
            elif gold and not pred:
                fn += 1
            else:
                tn += 1
    precision, recall, f1 = prf(tp, fp, fn)
    cells[f"{judge}_on_{gen}"] = {"n": n, "gold_pos": gold_pos, "tp": tp, "fp": fp, "tn": tn, "fn": fn, "precision": precision, "recall": recall, "f1": f1, "wrong_claim_contains": [wc_num, wc_den, pct(wc_num, wc_den)], "citation_locality": [cite_num, cite_den, pct(cite_num, cite_den)]}
row_avg = {j: round(sum(cells[f"{j}_on_{g}"]["f1"] for g in ["GPT", "Grok", "Gemini"]) / 3, 3) for j in ["GPT", "Grok", "Gemini"]}
col_avg = {g: round(sum(cells[f"{j}_on_{g}"]["f1"] for j in ["GPT", "Grok", "Gemini"]) / 3, 3) for g in ["GPT", "Grok", "Gemini"]}
diag = [cells[f"{x}_on_{x}"]["f1"] for x in ["GPT", "Grok", "Gemini"]]
off = [cells[f"{j}_on_{g}"]["f1"] for j in ["GPT", "Grok", "Gemini"] for g in ["GPT", "Grok", "Gemini"] if j != g]
same = {}
for j in ["GPT", "Grok", "Gemini"]:
    own = cells[f"{j}_on_{j}"]
    cross = [cells[f"{j}_on_{g}"] for g in ["GPT", "Grok", "Gemini"] if g != j]
    same[j] = {"f1_own": own["f1"], "f1_cross": round(sum(c["f1"] for c in cross) / 2, 3), "f1_delta": round(own["f1"] - sum(c["f1"] for c in cross) / 2, 3), "recall_own": own["recall"], "recall_cross": round(sum(c["recall"] for c in cross) / 2, 3), "recall_delta": round(own["recall"] - sum(c["recall"] for c in cross) / 2, 3), "precision_own": own["precision"], "precision_cross": round(sum(c["precision"] for c in cross) / 2, 3)}
report["judge"] = {"total_verdicts": total_verdicts, "cells": cells, "row_avg_f1": row_avg, "col_avg_f1": col_avg, "diag_avg_f1": round(sum(diag) / 3, 3), "offdiag_avg_f1": round(sum(off) / 6, 3), "diag_minus_offdiag": round(sum(diag) / 3 - sum(off) / 6, 3), "same_effects": same, "pair_types": dict(pairs)}

assert report["core"]["n"] == 300 and report["core"]["unique_core_ids"] == 300
assert total_outputs == 900 and total_eval == 897 and total_verdicts == 2683
Path("audit_report.json").write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
print(json.dumps(report, indent=2, sort_keys=True))
