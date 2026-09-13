"""Build the behavior x confusion-cell review queue.

For every (generator-behavior, judge-outcome) group in the validated set —
behavior in {context_follow, both_claims, memory_override, conflict_awareness,
refusal_or_insufficient, unrelated_or_failed, UNLABELED} x cell in {TP, FP, FN,
TN} — sample up to N_CAP verdicts (all if fewer) for human adjudication.

The human records two things per case (decided in the dashboard):
    human_gold_ok   - is the gold label correct? (did the answer really do what
                      its gold class implies?)
    human_judge_ok  - did the judge make the right flag / no-flag call vs the
                      ORIGINAL passages?
Everything else (false alarm / alternate error / mislabel / genuine miss) is
derived from those two plus the cell.

READ-ONLY over raw JSONL. No models are rerun, no raw data modified.

Run:  python paper/audit/build_cell_review_queue.py
Seed: CELL_QUEUE_SEED (default 20260627); cap: CELL_QUEUE_CAP (default 12).
"""
from __future__ import annotations

import csv
import json
import os
import random
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUDIT_DIR = Path(__file__).resolve().parent

GATES = ["type_valid", "answer_causal", "global_context_consistent", "no_original_answer_leakage", "original_contradicts_perturbed"]
PROVIDER_OF = {"azure-gpt": "GPT", "grok": "Grok", "gemini": "Gemini"}
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
BEHAVIOR_ORDER = ["context_follow", "both_claims", "memory_override", "conflict_awareness", "refusal_or_insufficient", "unrelated_or_failed", "UNLABELED"]
CELL_ORDER = ["TP", "FP", "FN", "TN"]

SEED = int(os.environ.get("CELL_QUEUE_SEED", "20260627"))
N_CAP = int(os.environ.get("CELL_QUEUE_CAP", "12"))

HUMAN_COLUMNS = ["human_gold_ok", "human_judge_ok", "human_notes"]
CSV_COLUMNS = [
    "case_id", "behavior", "cell", "core_id", "generator", "judge", "same_deployment",
    "question", "generator_answer", "gold_has_induced_error", "contains_factual_error",
    "original_value", "perturbed_value", "atomic_claim_original", "atomic_claim_perturbed",
    "wrong_claim", "judge_explanation", "supporting_source_passage_id", "supporting_source_passage_text",
    "modified_passage_ids", "auto_target_match", "auto_localization_match", "auto_artifact",
] + HUMAN_COLUMNS

REFUSAL_CONFLICT = {"refusal_or_insufficient", "conflict_awareness"}
_META = ["passage", "do not discuss", "does not discuss", "do not mention", "does not mention",
         "do not address", "does not address", "don't", "not provide", "insufficient", "cannot answer",
         "cannot fully", "no information", "not contain", "not specifically", "not discussed", "inference",
         "provided evidence", "not enough", "do not state", "does not state", "not specify"]


def rows(path):
    return [json.loads(x) for x in (ROOT / path).read_text(encoding="utf-8").splitlines() if x.strip()]


def passes(record):
    v = record.get("validation") or {}
    return all(v.get(g) is True for g in GATES)


_norm = re.compile(r"[\s\W_]+")
def norm(s):
    return _norm.sub(" ", (s or "").lower()).strip()


def is_meta(t):
    t = (t or "").lower()
    return any(m in t for m in _META)


def short_core(c):
    return (c or "").replace("garage_core_", "")


def passage_index(record, key):
    out = {}
    for p in record.get(key) or []:
        pid = p.get("passage_id")
        try:
            pid = int(pid)
        except (TypeError, ValueError):
            pass
        out[pid] = p.get("text") or ""
    return out


def modified_detail(record):
    orig = passage_index(record, "all_grounding_original")
    pert = passage_index(record, "all_grounding_perturbed")
    spans = {}
    for d in record.get("doc_modifications") or []:
        if not d.get("was_modified"):
            continue
        pid = d.get("passage_id")
        try:
            pid = int(pid)
        except (TypeError, ValueError):
            pass
        spans[pid] = {"original_span": d.get("original_span"), "perturbed_span": d.get("perturbed_span")}
    out = []
    for pid in record.get("modified_passage_ids") or []:
        try:
            pid = int(pid)
        except (TypeError, ValueError):
            pass
        out.append({"passage_id": pid, "original_text": orig.get(pid, ""), "perturbed_text": pert.get(pid, ""),
                    "original_span": (spans.get(pid) or {}).get("original_span"),
                    "perturbed_span": (spans.get(pid) or {}).get("perturbed_span")})
    return out


# behavior labels (llm_eval only — matches Table 1)
behavior_of = {}
for gen, path in LABEL_RUNS.items():
    for r in rows(path):
        for o in r.get("generator_outputs") or []:
            behavior_of[(r["core_id"], gen, o.get("sample_id"))] = (o.get("llm_eval") or {}).get("behavior_label")

core = rows("data/exp/3provider_300.jsonl")
validated_ids = {r["core_id"] for r in core if passes(r)}


def build():
    cases = []
    for (judge, gen), path in JUDGE_RUNS.items():
        for r in rows(path):
            if r["core_id"] not in validated_ids:
                continue
            orig = passage_index(r, "all_grounding_original")
            outs = {o.get("sample_id"): o for o in r.get("generator_outputs") or []}
            modified = []
            for m in r.get("modified_passage_ids") or []:
                try:
                    modified.append(int(m))
                except (TypeError, ValueError):
                    modified.append(m)
            for v in r.get("judge_verdicts") or []:
                sid = v.get("generator_sample_id")
                beh = behavior_of.get((r["core_id"], gen, sid)) or "UNLABELED"
                gold = bool(v.get("gold_has_induced_error"))
                pred = bool(v.get("contains_factual_error"))
                cell = ("TP" if gold and pred else "FN" if gold and not pred else "FP" if pred else "TN")
                o = outs.get(sid, {})
                wrong = v.get("wrong_claim") or ""
                sup = v.get("supporting_source_passage_id")
                sup_i = None
                if sup is not None:
                    try:
                        sup_i = int(sup)
                    except (TypeError, ValueError):
                        sup_i = None
                repl = v.get("gold_perturbation_replacement") or r.get("perturbed_value")
                cases.append({
                    "case_id": f"{judge}-on-{gen}__{short_core(r['core_id'])}",
                    "behavior": beh, "cell": cell, "group": f"{beh}/{cell}",
                    "core_id": r["core_id"], "generator": gen, "judge": judge, "same_deployment": judge == gen,
                    "question": r.get("question"),
                    "generator_answer": o.get("answer_text") or "",
                    "gold_has_induced_error": gold, "contains_factual_error": pred,
                    "original_value": r.get("original_value"), "perturbed_value": r.get("perturbed_value"),
                    "atomic_claim_original": r.get("atomic_claim_original"), "atomic_claim_perturbed": r.get("atomic_claim_perturbed"),
                    "perturbation_type": r.get("perturbation_type"),
                    "wrong_claim": wrong, "judge_explanation": v.get("explanation") or "", "judge_confidence": v.get("confidence"),
                    "supporting_source_passage_id": sup_i if sup_i is not None else sup,
                    "supporting_source_passage_text": orig.get(sup_i, "") if sup_i is not None else "",
                    "modified_passage_ids": modified, "modified_detail": modified_detail(r),
                    "all_original_passages": [{"passage_id": pid, "text": t} for pid, t in orig.items()],
                    "entails_original_claim": (o.get("llm_eval") or {}).get("entails_original_claim"),
                    "entails_perturbed_claim": (o.get("llm_eval") or {}).get("entails_perturbed_claim"),
                    "auto_target_match": (norm(repl) in norm(wrong)) if (repl and wrong) else None,
                    "auto_localization_match": (sup_i in modified) if sup_i is not None else None,
                    "auto_artifact": ("likely_artifact" if is_meta(wrong) else "substantive_claim") if (cell == "FP" and beh in REFUSAL_CONFLICT) else "",
                })
    return cases


def sample(cases):
    rnd = random.Random(SEED)
    by_group = defaultdict(list)
    for c in cases:
        by_group[(c["behavior"], c["cell"])].append(c)
    selected = []
    group_meta = {}
    for beh in BEHAVIOR_ORDER:
        for cell in CELL_ORDER:
            pool = by_group.get((beh, cell), [])
            if not pool:
                continue
            pool_sorted = sorted(pool, key=lambda c: c["case_id"])
            take = pool_sorted if len(pool_sorted) <= N_CAP else rnd.sample(pool_sorted, N_CAP)
            take = sorted(take, key=lambda c: c["case_id"])
            for c in take:
                c["group_total"] = len(pool)
                selected.append(c)
            group_meta[f"{beh}/{cell}"] = {"behavior": beh, "cell": cell, "total": len(pool), "sampled": len(take)}
    return selected, group_meta


def write(selected, group_meta):
    (AUDIT_DIR / "cell_review_queue.json").write_text(json.dumps({
        "meta": {"description": "behavior x confusion-cell review queue (validated set).",
                 "seed": SEED, "cap_per_cell": N_CAP, "n_cases": len(selected), "read_only": True,
                 "schema": "human_gold_ok (is the gold right?) + human_judge_ok (did the judge call it right vs the source?)",
                 "groups": group_meta},
        "cases": selected,
    }, indent=2), encoding="utf-8")

    prior = {}
    csv_path = AUDIT_DIR / "cell_review_queue.csv"
    if csv_path.exists():
        with csv_path.open(encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                prior[r.get("case_id")] = {k: r.get(k, "") for k in HUMAN_COLUMNS}
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        w.writeheader()
        for c in selected:
            row = {k: c.get(k) for k in CSV_COLUMNS}
            row["modified_passage_ids"] = ";".join(str(x) for x in (c.get("modified_passage_ids") or []))
            txt = c.get("supporting_source_passage_text") or ""
            row["supporting_source_passage_text"] = txt if len(txt) <= 1000 else txt[:997] + "..."
            for k in HUMAN_COLUMNS:
                row[k] = (prior.get(c["case_id"], {}) or {}).get(k, "")
            w.writerow(row)
    return csv_path


def main():
    cases = build()
    selected, group_meta = sample(cases)
    csv_path = write(selected, group_meta)
    from collections import Counter
    print(f"Built cell-review queue: {len(selected)} cases (cap {N_CAP}/cell, seed {SEED})")
    print(f"{'behavior':26s}" + "".join(f"{c:>8}" for c in CELL_ORDER))
    for beh in BEHAVIOR_ORDER:
        cells = {cell: group_meta.get(f"{beh}/{cell}") for cell in CELL_ORDER}
        if not any(cells.values()):
            continue
        line = f"{beh:26s}"
        for cell in CELL_ORDER:
            m = cells[cell]
            line += f"{(str(m['sampled'])+'/'+str(m['total'])) if m else '-':>8}"
        print(line)
    print(f"Wrote {csv_path.relative_to(ROOT)} and cell_review_queue.json")


if __name__ == "__main__":
    main()
