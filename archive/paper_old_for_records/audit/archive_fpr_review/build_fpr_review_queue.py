"""Build the human-review queue for the FPR / target-negative audit (Agent 2).

This answers one reviewer-risk question raised after the paired analysis:

    When a judge flags a "gold-negative" answer (one that does NOT contain the
    planted target error), is the judge actually WRONG, or did it find a
    different real source-grounding error?

The paired analysis found same-deployment judges flag target-negative answers
LESS often. But "target-negative" only means the planted perturbation is absent;
the judge prompt asks about ANY factual error, so some "false positives" may be
legitimate alternate errors. A human must adjudicate a focused sample.

This script is strictly READ-ONLY over the raw JSONL. It builds a prioritized
queue and writes:
    paper/audit/fpr_review_queue.csv   (spec columns + blank human columns)
    paper/audit/fpr_review_queue.json  (richer, drives the dashboard)

It does NOT rerun models, relabel with an LLM, or modify raw data.

Run:  python paper/audit/build_fpr_review_queue.py
Seed: FPR_QUEUE_SEED (default 20260627) for reproducible sampling.
"""
from __future__ import annotations

import csv
import json
import os
import random
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUDIT_DIR = Path(__file__).resolve().parent

PROVIDERS = ["GPT", "Grok", "Gemini"]
PROVIDER_OF = {"azure-gpt": "GPT", "grok": "Grok", "gemini": "Gemini"}
GATES = [
    "type_valid",
    "answer_causal",
    "global_context_consistent",
    "no_original_answer_leakage",
    "original_contradicts_perturbed",
]
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
EXAMPLES_PATH = "paper/audit/examples_report.json"

SEED = int(os.environ.get("FPR_QUEUE_SEED", "20260627"))
N_FALSE_NEG_PER_GEN = 10        # P4: 30 total, balanced
N_SANITY_TP = 15                # P5
N_SANITY_TN = 15                # P5

# Human columns (filled in the dashboard / by hand).
HUMAN_COLUMNS = [
    "human_target_present",
    "human_judge_detected_target",
    "human_alternate_valid_error",
    "human_artifact",
    "human_false_alarm",
    "human_localization_correct",
    "human_notes",
]

# Auto-triage for refusal/conflict apparent-FPs: did the judge flag a *meta-claim
# about the passages* (e.g. "the passages do not discuss X") rather than a
# substantive factual assertion? Meta-claims are the perturbation artifact (the
# answer commented on the perturbed source; the judge scores it against the
# original), so they are very likely NOT genuine false alarms.
REFUSAL_CONFLICT = {"refusal_or_insufficient", "conflict_awareness"}
_META_MARKERS = [
    "passage", "do not discuss", "does not discuss", "do not mention", "does not mention",
    "do not address", "does not address", "don't", "not provide", "insufficient",
    "cannot answer", "cannot fully", "no information", "not contain", "not specifically",
    "not discussed", "inference", "provided evidence", "not enough", "do not state",
    "does not state", "not specify", "do not specify",
]


def is_meta_claim(text):
    t = (text or "").lower()
    return any(m in t for m in _META_MARKERS)


def auto_artifact_tag(category, behavior_label, wrong_claim):
    """'' for non-applicable; else 'likely_artifact' / 'substantive_claim'."""
    if category != "apparent_fp" or behavior_label not in REFUSAL_CONFLICT:
        return ""
    return "likely_artifact" if is_meta_claim(wrong_claim) else "substantive_claim"
# CSV columns, exactly per the task spec, then the human columns.
CSV_COLUMNS = [
    "case_id",
    "core_id",
    "is_validated",
    "generator",
    "judge",
    "pair_type",
    "question",
    "generator_answer",
    "behavior_label",
    "entails_original_claim",
    "entails_perturbed_claim",
    "gold_has_induced_error",
    "contains_factual_error",
    "original_value",
    "perturbed_value",
    "atomic_claim_original",
    "atomic_claim_perturbed",
    "wrong_claim",
    "judge_explanation",
    "supporting_source_passage_id",
    "supporting_source_passage_text",
    "modified_passage_ids",
    "auto_target_match",
    "auto_localization_match",
    "auto_artifact",
    "subset",
    "priority",
    "paper_example",
] + HUMAN_COLUMNS


def rows(path):
    return [json.loads(x) for x in (ROOT / path).read_text(encoding="utf-8").splitlines() if x.strip()]


def passes(record):
    v = record.get("validation") or {}
    return all(v.get(g) is True for g in GATES)


_norm_re = re.compile(r"[\s\W_]+")


def norm(s):
    return _norm_re.sub(" ", (s or "").lower()).strip()


def short_core(core_id):
    return (core_id or "").replace("garage_core_", "")


def first(*vals):
    for v in vals:
        if v not in (None, ""):
            return v
    return None


# --------------------------------------------------------------------------- #
# Pass 1: read every verdict into a rich case dict (validated + a few examples)
# --------------------------------------------------------------------------- #
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
    """For each modified passage: original text, perturbed text, the edited span."""
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
    detail = []
    for pid in record.get("modified_passage_ids") or []:
        try:
            pid_i = int(pid)
        except (TypeError, ValueError):
            pid_i = pid
        detail.append(
            {
                "passage_id": pid_i,
                "original_text": orig.get(pid_i, ""),
                "perturbed_text": pert.get(pid_i, ""),
                "original_span": (spans.get(pid_i) or {}).get("original_span"),
                "perturbed_span": (spans.get(pid_i) or {}).get("perturbed_span"),
            }
        )
    return detail


def build_cases():
    cases = {}  # case_id -> dict
    for (judge, gen), path in JUDGE_RUNS.items():
        for record in rows(path):
            core_id = record["core_id"]
            is_valid = passes(record)
            orig_passages = passage_index(record, "all_grounding_original")
            # answer text + generation-side labels, matched by sample_id
            gen_outputs = {o.get("sample_id"): o for o in (record.get("generator_outputs") or [])}
            modified_ids = record.get("modified_passage_ids") or []
            modified_ids_int = []
            for m in modified_ids:
                try:
                    modified_ids_int.append(int(m))
                except (TypeError, ValueError):
                    modified_ids_int.append(m)
            for v in record.get("judge_verdicts") or []:
                sid = v.get("generator_sample_id")
                out = gen_outputs.get(sid, {})
                gold = bool(v.get("gold_has_induced_error"))
                pred = bool(v.get("contains_factual_error"))
                if gold and pred:
                    category = "true_positive"
                elif (not gold) and pred:
                    category = "apparent_fp"   # gold-negative flagged
                elif gold and not pred:
                    category = "false_negative"
                else:
                    category = "true_negative"

                wrong_claim = v.get("wrong_claim") or ""
                replacement = first(v.get("gold_perturbation_replacement"), record.get("perturbed_value"))
                auto_target_match = (norm(replacement) in norm(wrong_claim)) if (replacement and wrong_claim) else None

                sup = v.get("supporting_source_passage_id")
                sup_int = None
                if sup is not None:
                    try:
                        sup_int = int(sup)
                    except (TypeError, ValueError):
                        sup_int = None
                auto_loc = (sup_int in modified_ids_int) if sup_int is not None else None
                sup_text = orig_passages.get(sup_int, "") if sup_int is not None else ""

                # llm_eval label only (Table 1 source); blank if the output was unlabeled.
                behavior = (out.get("llm_eval") or {}).get("behavior_label")
                cid = f"{judge}-on-{gen}__{short_core(core_id)}"
                cases[cid] = {
                    "case_id": cid,
                    "core_id": core_id,
                    "is_validated": is_valid,
                    "generator": gen,
                    "judge": judge,
                    "same_deployment": judge == gen,
                    "pair_type": v.get("pair_type"),
                    "category": category,
                    "question": record.get("question"),
                    "question_category": record.get("question_category"),
                    "generator_answer": out.get("answer_text") or "",
                    "is_refusal": out.get("is_refusal"),
                    "cited_passage_ids": out.get("cited_passage_ids") or [],
                    "behavior_label": behavior,
                    "entails_original_claim": first(out.get("entails_original_claim"), (out.get("llm_eval") or {}).get("entails_original_claim")),
                    "entails_perturbed_claim": first(out.get("entails_perturbed_claim"), (out.get("llm_eval") or {}).get("entails_perturbed_claim")),
                    "gold_has_induced_error": gold,
                    "contains_factual_error": pred,
                    "perturbation_type": record.get("perturbation_type"),
                    "original_value": record.get("original_value"),
                    "perturbed_value": record.get("perturbed_value"),
                    "atomic_claim_original": record.get("atomic_claim_original"),
                    "atomic_claim_perturbed": record.get("atomic_claim_perturbed"),
                    "wrong_claim": wrong_claim,
                    "judge_explanation": v.get("explanation") or "",
                    "judge_confidence": v.get("confidence"),
                    "supporting_source_passage_id": sup_int if sup_int is not None else sup,
                    "supporting_source_passage_text": sup_text,
                    "modified_passage_ids": modified_ids_int,
                    "modified_detail": modified_detail(record),
                    "all_original_passages": [{"passage_id": pid, "text": txt} for pid, txt in orig_passages.items()],
                    "auto_target_match": auto_target_match,
                    "auto_localization_match": auto_loc,
                    "auto_artifact": auto_artifact_tag(category, behavior, wrong_claim),
                }
    return cases


# --------------------------------------------------------------------------- #
# Pass 2: identify paper examples (must be verified) from examples_report.json
# --------------------------------------------------------------------------- #
def paper_example_ids(cases):
    try:
        ex = json.loads((ROOT / EXAMPLES_PATH).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return set()
    wanted = []  # (cell, normalized question)
    for _, e in (ex.get("judge_examples") or {}).items():
        cell = e.get("cell")  # e.g. "Grok_on_GPT" == judge_on_generator
        q = norm(e.get("question"))
        if cell and q:
            wanted.append((cell, q))
    ids = set()
    for cid, c in cases.items():
        cell = f"{c['judge']}_on_{c['generator']}"
        cq = norm(c.get("question"))
        for wcell, wq in wanted:
            # questions are truncated in the examples file; prefix match is enough
            if cell == wcell and (cq.startswith(wq) or wq.startswith(cq[: len(wq)])):
                ids.add(cid)
    return ids


# --------------------------------------------------------------------------- #
# Pass 3: prioritized selection
# --------------------------------------------------------------------------- #
def select_queue(cases):
    rnd = random.Random(SEED)
    valid = {cid: c for cid, c in cases.items() if c["is_validated"]}

    def pool(category, same=None):
        out = [c for c in valid.values() if c["category"] == category and (same is None or c["same_deployment"] == same)]
        return out

    selected = {}  # cid -> (subset, priority)

    def add(c, subset, priority):
        if c["case_id"] not in selected:
            selected[c["case_id"]] = (subset, priority)

    # P1: ALL same-deployment apparent FPs
    same_fp = pool("apparent_fp", same=True)
    for c in same_fp:
        add(c, "same_fp", 1)
    # generator mix of P1, to match P2
    p1_by_gen = {g: sum(1 for c in same_fp if c["generator"] == g) for g in PROVIDERS}

    # P2: cross-deployment apparent FPs, matched to P1 per-generator counts
    for g in PROVIDERS:
        cross_g = [c for c in pool("apparent_fp", same=False) if c["generator"] == g]
        rnd.shuffle(cross_g)
        for c in cross_g[: p1_by_gen.get(g, 0)]:
            add(c, "cross_fp", 2)

    # P4: 30 false negatives balanced across generators
    for g in PROVIDERS:
        fn_g = [c for c in pool("false_negative") if c["generator"] == g]
        rnd.shuffle(fn_g)
        for c in fn_g[:N_FALSE_NEG_PER_GEN]:
            add(c, "false_negative", 4)

    # P5: sanity TP / TN, spread across cells for coverage
    def stratified(cands, n):
        rnd.shuffle(cands)
        by_cell = {}
        for c in cands:
            by_cell.setdefault((c["judge"], c["generator"]), []).append(c)
        picked, i = [], 0
        cells = list(by_cell.values())
        while len(picked) < n and any(cells):
            bucket = cells[i % len(cells)]
            if bucket:
                picked.append(bucket.pop())
            i += 1
            if i > 10000:
                break
        return picked[:n]

    for c in stratified(pool("true_positive"), N_SANITY_TP):
        add(c, "sanity_tp", 5)
    for c in stratified(pool("true_negative"), N_SANITY_TN):
        add(c, "sanity_tn", 5)

    # P3: paper examples (include regardless of validation/category); highest priority tag
    pe_ids = paper_example_ids(cases)
    for cid in pe_ids:
        c = cases[cid]
        if cid in selected:
            # keep its subset but flag as paper example via priority bump handled below
            pass
        else:
            add(c, "paper_example", 3)

    # Assemble ordered list
    out = []
    for cid, (subset, priority) in selected.items():
        c = dict(cases[cid])
        c["subset"] = subset
        c["priority"] = priority
        c["paper_example"] = cid in pe_ids
        out.append(c)

    # Order: priority asc, then same-before-cross, then generator, then judge
    order_gen = {g: i for i, g in enumerate(PROVIDERS)}
    out.sort(key=lambda c: (c["priority"], not c["same_deployment"], order_gen.get(c["generator"], 9), order_gen.get(c["judge"], 9), c["core_id"]))
    return out


# --------------------------------------------------------------------------- #
# Write outputs
# --------------------------------------------------------------------------- #
def write_outputs(queue):
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    # JSON (rich) — drives the dashboard
    (AUDIT_DIR / "fpr_review_queue.json").write_text(
        json.dumps(
            {
                "meta": {
                    "description": "FPR / target-negative human-review queue (targeted author audit).",
                    "seed": SEED,
                    "n_cases": len(queue),
                    "read_only": True,
                    "label": "targeted author audit / manual adjudication sample",
                },
                "cases": queue,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    # CSV (spec columns + blank human columns). Preserve existing human labels
    # if a previous CSV exists, so a rebuild never clobbers human work.
    prior = {}
    csv_path = AUDIT_DIR / "fpr_review_queue.csv"
    if csv_path.exists():
        with csv_path.open(encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                prior[r.get("case_id")] = {k: r.get(k, "") for k in HUMAN_COLUMNS}

    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        w.writeheader()
        for c in queue:
            row = {k: c.get(k) for k in CSV_COLUMNS}
            row["modified_passage_ids"] = ";".join(str(x) for x in (c.get("modified_passage_ids") or []))
            # keep passage text readable but bounded in the CSV (full text is in JSON)
            txt = c.get("supporting_source_passage_text") or ""
            row["supporting_source_passage_text"] = txt if len(txt) <= 1000 else txt[:997] + "..."
            for k in HUMAN_COLUMNS:
                row[k] = (prior.get(c["case_id"], {}) or {}).get(k, "")
            w.writerow(row)

    return csv_path


def main():
    cases = build_cases()
    queue = select_queue(cases)
    csv_path = write_outputs(queue)

    from collections import Counter
    subset_counts = Counter(c["subset"] for c in queue)
    cat_counts = Counter((c["category"], "same" if c["same_deployment"] else "cross") for c in queue)
    print(f"Built FPR review queue: {len(queue)} cases (seed {SEED})")
    print("By subset:", dict(subset_counts))
    print("Paper examples flagged:", sum(1 for c in queue if c["paper_example"]))
    print(f"Wrote: {csv_path.relative_to(ROOT)} and fpr_review_queue.json")


if __name__ == "__main__":
    main()
