"""Generate the data-driven appendix for the audit dossier.

Read-only over cell_review_queue.json + cell_review_progress.json. Emits:
    paper/audit/cell_audit_findings.md     coverage grid, per-cell tallies,
                                           same/cross splits, rule-of-three
                                           bounds, gold quality, FULL per-case log
    paper/audit/cell_audit_findings.json   same numbers, machine-readable

Re-run any time after labelling more cases; the numbers + log update.
Run: python paper/audit/gen_audit_dossier.py
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

AUDIT_DIR = Path(__file__).resolve().parent
QUEUE = AUDIT_DIR / "cell_review_queue.json"
PROGRESS = AUDIT_DIR / "cell_review_progress.json"

BEHAVIOR_ORDER = ["context_follow", "both_claims", "memory_override", "conflict_awareness", "refusal_or_insufficient", "unrelated_or_failed", "UNLABELED"]
CELL_ORDER = ["TP", "FP", "FN", "TN"]


def done(p):
    return bool(p.get("human_gold_ok")) and bool(p.get("human_judge_ok"))


def derive(cell, g, j):
    """Map (cell, gold_ok, judge_ok) -> plain-English verdict."""
    if cell == "TP":
        if g == "yes" and j == "yes":
            return "genuine TP"
        if g == "no":
            return "gold mislabel (answer did not adopt)"
        if j == "no":
            return "right verdict, wrong reason"
        return "unclear"
    if cell == "FP":
        if g == "no":
            return "gold mislabel (answer DID adopt -> really TP)"
        if g == "yes" and j == "no":
            return "genuine false alarm"
        if g == "yes" and j == "yes":
            return "judge caught a real / alternate error"
        return "unclear"
    if cell == "FN":
        if g == "no":
            return "gold too aggressive (answer did not adopt)"
        if g == "yes" and j == "no":
            return "genuine miss"
        if g == "yes" and j == "yes":
            return "INCONSISTENT (gold+ but judge right to be silent)"
        return "unclear"
    if cell == "TN":
        if g == "yes" and j == "yes":
            return "genuine TN"
        if j == "no":
            return "judge MISSED a real error"
        if g == "no":
            return "gold mislabel (answer DID adopt)"
        return "unclear"
    return "unclear"


def rule_of_three(events, n):
    """95% one-sided bound for a 0- or all-event proportion (events/n)."""
    if n == 0:
        return None
    if events == 0:
        return f"0/{n}; 95% upper bound ~{100*3.0/n:.0f}% (rule of three)"
    if events == n:
        return f"{n}/{n}; 95% lower bound ~{100*(1-3.0/n):.0f}% (rule of three)"
    return f"{events}/{n} = {100*events/n:.0f}%"


def main():
    cases = {c["case_id"]: c for c in json.loads(QUEUE.read_text())["cases"]}
    progress = json.loads(PROGRESS.read_text()) if PROGRESS.exists() else {}
    reviewed = []
    for cid, p in progress.items():
        if not done(p):
            continue
        c = cases.get(cid)
        if not c:
            continue
        reviewed.append((cid, c, p))

    sampled = defaultdict(int)
    for c in cases.values():
        sampled[(c["behavior"], c["cell"])] += 1
    rev = defaultdict(int)
    for cid, c, p in reviewed:
        rev[(c["behavior"], c["cell"])] += 1

    # per-cell derivation tallies + same/cross
    cell_tally = defaultdict(Counter)        # cell -> Counter(derived)
    cell_arm = defaultdict(lambda: defaultdict(Counter))  # cell -> arm -> Counter(judge_ok)
    behcell_log = defaultdict(list)
    gold_issues = []
    for cid, c, p in reviewed:
        cell = c["cell"]
        d = derive(cell, p.get("human_gold_ok"), p.get("human_judge_ok"))
        cell_tally[cell][d] += 1
        arm = "same" if c.get("same_deployment") else "cross"
        cell_arm[cell][arm][p.get("human_judge_ok")] += 1
        behcell_log[(c["behavior"], cell)].append((cid, c, p, d))
        if p.get("human_gold_ok") != "yes":
            gold_issues.append((cid, c, p))

    fp_n = sum(cell_tally["FP"].values())
    fp_falsealarm = cell_tally["FP"].get("genuine false alarm", 0)
    tn_n = sum(cell_tally["TN"].values())
    tn_missed = cell_tally["TN"].get("judge MISSED a real error", 0)

    report = {
        "n_reviewed": len(reviewed),
        "n_total": len(cases),
        "coverage": {f"{b}/{c}": {"reviewed": rev[(b, c)], "sampled": sampled[(b, c)]}
                     for b in BEHAVIOR_ORDER for c in CELL_ORDER if sampled[(b, c)]},
        "cell_tally": {k: dict(v) for k, v in cell_tally.items()},
        "fp_false_alarm_bound": rule_of_three(fp_falsealarm, fp_n),
        "tn_missed_error_bound": rule_of_three(tn_missed, tn_n),
        "gold_issue_rate": f"{len(gold_issues)}/{len(reviewed)}",
        "gold_issue_locations": dict(Counter(f"{c['behavior']}/{c['cell']}" for _, c, _ in gold_issues)),
    }
    (AUDIT_DIR / "cell_audit_findings.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    # ---------------- markdown ----------------
    L = ["# Cell audit — findings & per-case log (auto-generated)", "",
         f"_Generated by `gen_audit_dossier.py` from `cell_review_progress.json`. "
         f"Reviewed **{len(reviewed)} / {len(cases)}** cases. Re-run to refresh._", ""]

    L.append("## Coverage (reviewed / sampled, by behavior × cell)")
    L.append("")
    L.append("| Behavior | TP | FP | FN | TN |")
    L.append("|---|---|---|---|---|")
    for b in BEHAVIOR_ORDER:
        row = [b]
        for cell in CELL_ORDER:
            s = sampled[(b, cell)]
            row.append(f"{rev[(b, cell)]}/{s}" if s else "–")
        L.append("| " + " | ".join(row) + " |")
    L.append("")
    L.append("_sampled = how many of that cell's full population were put in the queue (cap 12); "
             "the cell population sizes are in `behavior_stratified_report.json`._")
    L.append("")

    L.append("## Findings by cell")
    L.append("")
    for cell in CELL_ORDER:
        t = cell_tally[cell]
        if not sum(t.values()):
            continue
        L.append(f"### {cell}  (n={sum(t.values())})")
        for d, n in t.most_common():
            L.append(f"- {n} — {d}")
        if cell in ("FP", "TN"):
            for arm in ("same", "cross"):
                jc = dict(cell_arm[cell][arm])
                L.append(f"  - {arm}: n={sum(jc.values())}, judge_ok={jc}")
        L.append("")
    L.append(f"**False-alarm rate (FP):** {report['fp_false_alarm_bound']}")
    L.append("")
    L.append(f"**Missed-error rate (TN):** {report['tn_missed_error_bound']}")
    L.append("")
    L.append(f"**Gold-label issues** (gold_ok != yes): {report['gold_issue_rate']} — by location: {report['gold_issue_locations']}")
    L.append("")

    L.append("## Per-case adjudication log")
    L.append("")
    L.append("Every reviewed case, grouped by behavior × cell. `g`/`j` = your gold_ok / judge_ok calls.")
    L.append("")
    for b in BEHAVIOR_ORDER:
        for cell in CELL_ORDER:
            items = behcell_log.get((b, cell))
            if not items:
                continue
            L.append(f"### {b} / {cell}  ({len(items)})")
            L.append("")
            L.append("| case_id | gen→judge | dep | g | j | derived | notes |")
            L.append("|---|---|---|---|---|---|---|")
            for cid, c, p, d in sorted(items, key=lambda x: x[0]):
                dep = "same" if c.get("same_deployment") else "cross"
                g = p.get("human_gold_ok") or "·"
                j = p.get("human_judge_ok") or "·"
                notes = (p.get("human_notes") or "").replace("|", "/").replace("\n", " ")
                L.append(f"| `{cid}` | {c['generator']}→{c['judge']} | {dep} | {g} | {j} | {d} | {notes} |")
            L.append("")
            # include the question for context, compactly
            L.append("<details><summary>questions</summary>")
            L.append("")
            for cid, c, p, d in sorted(items, key=lambda x: x[0]):
                L.append(f"- `{cid}` — {(c.get('question') or '').strip()}")
            L.append("")
            L.append("</details>")
            L.append("")

    (AUDIT_DIR / "cell_audit_findings.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"Reviewed {len(reviewed)}/{len(cases)}.")
    print(f"FP false-alarm: {report['fp_false_alarm_bound']}")
    print(f"TN missed-error: {report['tn_missed_error_bound']}")
    print(f"Gold issues: {report['gold_issue_rate']} {report['gold_issue_locations']}")
    print("Wrote cell_audit_findings.md + cell_audit_findings.json")


if __name__ == "__main__":
    main()
