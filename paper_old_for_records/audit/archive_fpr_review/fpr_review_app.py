"""Local adjudication dashboard for the FPR / target-negative audit (Agent 2).

Serves paper/audit/fpr_review_dashboard.html and persists your judgments to disk
as you work. Nothing here reruns models or touches the raw JSONL — it only reads
the pre-built queue and writes audit outputs.

Persistence (all local):
    paper/audit/fpr_review_progress.json   <- live store, auto-saved on every edit
    paper/audit/fpr_review_queue.csv       <- human columns kept in sync
    paper/audit/fpr_review_summary.md      <- regenerated on every save
    paper/tables/fpr_audit_summary.tex     <- regenerated on every save

Usage:
    python paper/audit/build_fpr_review_queue.py     # build the queue first (once)
    python paper/audit/fpr_review_app.py             # launch dashboard (opens browser)
    python paper/audit/fpr_review_app.py --export    # just regenerate summary/CSV/tex
    python paper/audit/fpr_review_app.py --port 8000

Your judgments live in fpr_review_progress.json and survive restarts.
"""
from __future__ import annotations

import argparse
import csv
import json
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

AUDIT_DIR = Path(__file__).resolve().parent
ROOT = AUDIT_DIR.parents[1]
TABLES_DIR = ROOT / "paper" / "tables"

QUEUE_JSON = AUDIT_DIR / "fpr_review_queue.json"
QUEUE_CSV = AUDIT_DIR / "fpr_review_queue.csv"
PROGRESS_JSON = AUDIT_DIR / "fpr_review_progress.json"
DASHBOARD = AUDIT_DIR / "fpr_review_dashboard.html"
GUIDE = AUDIT_DIR / "fpr_review_guide.md"
SUMMARY_MD = AUDIT_DIR / "fpr_review_summary.md"
SUMMARY_TEX = TABLES_DIR / "fpr_audit_summary.tex"

HUMAN_COLUMNS = [
    "human_target_present",
    "human_judge_detected_target",
    "human_alternate_valid_error",
    "human_artifact",
    "human_false_alarm",
    "human_localization_correct",
    "human_notes",
]

_lock = threading.Lock()


# --------------------------------------------------------------------------- #
# Data access
# --------------------------------------------------------------------------- #
def load_queue():
    return json.loads(QUEUE_JSON.read_text(encoding="utf-8"))["cases"]


def load_progress():
    if PROGRESS_JSON.exists():
        try:
            return json.loads(PROGRESS_JSON.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def save_progress(progress):
    PROGRESS_JSON.write_text(json.dumps(progress, indent=2, sort_keys=True), encoding="utf-8")


def is_done(labels):
    return bool((labels or {}).get("human_false_alarm"))


# --------------------------------------------------------------------------- #
# Derived outputs: CSV sync, summary md, tex
# --------------------------------------------------------------------------- #
def sync_csv(progress):
    if not QUEUE_CSV.exists():
        return
    with QUEUE_CSV.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        fieldnames = reader.fieldnames or []
        rows = list(reader)
    for r in rows:
        labels = progress.get(r.get("case_id"), {})
        for k in HUMAN_COLUMNS:
            if k in fieldnames:
                r[k] = labels.get(k, "")
    with QUEUE_CSV.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


GROUPS = [
    ("Same-deployment target-negative flagged", lambda c: c["category"] == "apparent_fp" and c["same_deployment"]),
    ("Cross-deployment target-negative flagged", lambda c: c["category"] == "apparent_fp" and not c["same_deployment"]),
    ("False negatives", lambda c: c["category"] == "false_negative"),
    ("Sanity TP", lambda c: c["category"] == "true_positive"),
    ("Sanity TN", lambda c: c["category"] == "true_negative"),
]


def classify(labels):
    """Partition a reviewed case into one bucket (precedence order)."""
    if labels.get("human_judge_detected_target") == "yes":
        return "target"
    if labels.get("human_alternate_valid_error") == "yes":
        return "alternate"
    if labels.get("human_artifact") == "yes":
        return "artifact"
    if labels.get("human_false_alarm") == "yes":
        return "false_alarm"
    return "unclear"


def compute_summary(cases, progress):
    rows = []
    for label, pred in GROUPS:
        members = [c for c in cases if pred(c)]
        reviewed = [c for c in members if is_done(progress.get(c["case_id"], {}))]
        buckets = {"target": 0, "alternate": 0, "artifact": 0, "false_alarm": 0, "unclear": 0}
        for c in reviewed:
            buckets[classify(progress.get(c["case_id"], {}))] += 1
        rows.append(
            {
                "label": label,
                "n": len(members),
                "reviewed": len(reviewed),
                "target": buckets["target"],
                "alternate": buckets["alternate"],
                "artifact": buckets["artifact"],
                "false_alarm": buckets["false_alarm"],
                "unclear": buckets["unclear"],
            }
        )
    verdict = decide_case(rows)
    return {"rows": rows, "verdict": verdict}


def decide_case(rows):
    same = next((r for r in rows if r["label"].startswith("Same-deployment")), None)
    cross = next((r for r in rows if r["label"].startswith("Cross-deployment")), None)
    if not same or not cross or same["reviewed"] < max(5, same["n"] // 2) or cross["reviewed"] < max(5, cross["n"] // 2):
        return "Pending — review more apparent-FP cases (need roughly half of each group) before deciding Case A/B/C."

    def rate(r, key):
        return (r[key] / r["reviewed"]) if r["reviewed"] else 0.0

    alt_same, alt_cross = rate(same, "alternate"), rate(cross, "alternate")
    fa_same, fa_cross = rate(same, "false_alarm"), rate(cross, "false_alarm")
    if alt_same < 0.25 and alt_cross < 0.25:
        return (f"Case A (strong): most apparent FPs are real false alarms "
                f"(false-alarm rate same {fa_same:.0%} / cross {fa_cross:.0%}). "
                f"Keep: same-deployment judges produce fewer false alarms on their own generator's target-negative answers.")
    if alt_cross - alt_same > 0.15:
        return (f"Case C (soften): cross judges flag more partly because they catch more alternate valid errors "
                f"(alternate rate cross {alt_cross:.0%} vs same {alt_same:.0%}). "
                f"Reframe the FPR gap as a target-negative flag-rate difference driven by the target-vs-any-error label mismatch.")
    return (f"Case B (caveat): many apparent FPs are alternate valid errors, but at similar rates "
            f"(same {alt_same:.0%} / cross {alt_cross:.0%}). Claim survives with a noted caveat.")


def write_summary(cases, progress):
    s = compute_summary(cases, progress)
    # markdown
    L = ["# FPR / target-negative audit summary", "",
         "_Targeted author audit (manual adjudication sample). Auto-generated from `fpr_review_progress.json`._", ""]
    total = sum(r["n"] for r in s["rows"])
    rev = sum(r["reviewed"] for r in s["rows"])
    L.append(f"Progress: **{rev} / {total}** cases reviewed.")
    L.append("")
    L.append("| Audit subset | n | reviewed | target error | alternate valid | artifact | false alarm | unclear |")
    L.append("|---|---|---|---|---|---|---|---|")
    for r in s["rows"]:
        L.append(f"| {r['label']} | {r['n']} | {r['reviewed']} | {r['target']} | {r['alternate']} | {r['artifact']} | {r['false_alarm']} | {r['unclear']} |")
    L.append("")
    L.append("**Bucketing** (precedence): a reviewed flag is *target error* if the judge identified the planted error; "
             "else *alternate valid* if it caught a different real error; else *artifact* if it flagged a meta-claim about "
             "the passages (refusal/perturbation artifact); else *false alarm* if a genuine false alarm; else *unclear*.")
    L.append("")
    L.append(f"**Tentative interpretation:** {s['verdict']}")
    L.append("")
    L.append("For false negatives, `target error` here counts cases the human still judged as a genuine miss; "
             "use `human_target_present=no` in notes to flag gold that was too aggressive.")
    SUMMARY_MD.write_text("\n".join(L) + "\n", encoding="utf-8")

    # tex
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    T = ["% Auto-generated by paper/audit/fpr_review_app.py -- do not edit by hand.",
         r"\begin{table}[t]", r"\centering", r"\small",
         r"\begin{tabular}{l rrrrrr}", r"\toprule",
         r"Audit subset & $n$ & target & alt.\ valid & artifact & false alarm & unclear \\", r"\midrule"]
    for r in s["rows"]:
        # show reviewed counts; n in parens
        T.append(f"{r['label']} ({r['reviewed']}/{r['n']}) & {r['n']} & {r['target']} & {r['alternate']} & {r['artifact']} & {r['false_alarm']} & {r['unclear']} \\\\")
    T.append(r"\bottomrule")
    T.append(r"\end{tabular}")
    T.append(r"\caption{Targeted author audit of target-negative flagged cases (apparent false positives) and "
             r"false negatives. For each reviewed flag we record whether the judge caught the planted \emph{target} "
             r"error, a different \emph{alternate} valid source-grounding error, was a genuine \emph{false alarm}, "
             r"or was \emph{unclear}. Counts are reviewed/total in the row label.}")
    T.append(r"\label{tab:fpr-audit}")
    T.append(r"\end{table}")
    SUMMARY_TEX.write_text("\n".join(T) + "\n", encoding="utf-8")
    return s


def regenerate_all():
    cases = load_queue()
    progress = load_progress()
    sync_csv(progress)
    s = write_summary(cases, progress)
    return cases, progress, s


# --------------------------------------------------------------------------- #
# HTTP server
# --------------------------------------------------------------------------- #
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body).encode("utf-8")
        elif isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            return self._send(200, DASHBOARD.read_text(encoding="utf-8"), "text/html; charset=utf-8")
        if self.path == "/api/queue":
            with _lock:
                cases = load_queue()
                progress = load_progress()
                summary = compute_summary(cases, progress)
            return self._send(200, {"cases": cases, "progress": progress, "summary": summary})
        if self.path == "/api/summary":
            with _lock:
                return self._send(200, compute_summary(load_queue(), load_progress()))
        if self.path == "/api/guide":
            txt = GUIDE.read_text(encoding="utf-8") if GUIDE.exists() else "Guide not found."
            return self._send(200, txt, "text/plain; charset=utf-8")
        return self._send(404, {"error": "not found"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            return self._send(400, {"error": "bad json"})

        if self.path == "/api/save":
            case_id = data.get("case_id")
            labels = data.get("labels") or {}
            clean = {k: labels.get(k, "") for k in HUMAN_COLUMNS}
            clean["updated_at"] = int(time.time())
            with _lock:
                progress = load_progress()
                progress[case_id] = clean
                save_progress(progress)
                cases = load_queue()
                sync_csv(progress)
                summary = write_summary(cases, progress)
            return self._send(200, {"ok": True, "progress": progress, "summary": summary})

        if self.path == "/api/export":
            with _lock:
                regenerate_all()
            return self._send(200, {"ok": True, "written": [
                str(QUEUE_CSV.relative_to(ROOT)), str(SUMMARY_MD.relative_to(ROOT)), str(SUMMARY_TEX.relative_to(ROOT))]})

        return self._send(404, {"error": "not found"})


def serve(port):
    if not QUEUE_JSON.exists():
        raise SystemExit("Queue not found. Run: python paper/audit/build_fpr_review_queue.py")
    # Safety: snapshot any existing judgements before serving, so a session can
    # never lose prior work.
    if PROGRESS_JSON.exists():
        bak = AUDIT_DIR / ("fpr_review_progress.backup-" + time.strftime("%Y%m%d-%H%M%S") + ".json")
        bak.write_text(PROGRESS_JSON.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"  backup:   {bak.relative_to(ROOT)}")
    regenerate_all()  # ensure derived files exist on launch
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/"
    print(f"FPR review dashboard → {url}")
    print(f"  queue:    {QUEUE_JSON.relative_to(ROOT)}")
    print(f"  progress: {PROGRESS_JSON.relative_to(ROOT)} (auto-saved)")
    print("  Ctrl-C to stop. Your judgments persist on disk.")
    try:
        webbrowser.open(url)
    except Exception:
        pass
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped. Progress saved.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--export", action="store_true", help="regenerate CSV/summary/tex from progress and exit")
    args = ap.parse_args()
    if args.export:
        cases, progress, s = regenerate_all()
        rev = sum(r["reviewed"] for r in s["rows"])
        print(f"Exported. Reviewed {rev}/{len(cases)}. Wrote summary + tex + synced CSV.")
        return
    serve(args.port)


if __name__ == "__main__":
    main()
