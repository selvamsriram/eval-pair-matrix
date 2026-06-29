"""Local dashboard for the behavior x confusion-cell review.

Serves cell_review_dashboard.html and persists judgements to disk as you work.
Read-only over the queue; writes only audit outputs.

Per case you record two calls:
    human_gold_ok  - is the gold label correct?
    human_judge_ok - did the judge make the right flag/no-flag call vs the source?

Persistence (local):
    paper/audit/cell_review_progress.json   <- live store, auto-saved each edit
    paper/audit/cell_review_queue.csv       <- human columns kept in sync
    paper/audit/cell_review_summary.md      <- regenerated on every save
    paper/tables/cell_audit_summary.tex     <- regenerated on every save

Usage:
    python paper/audit/build_cell_review_queue.py   # build queue (once)
    python paper/audit/cell_review_app.py           # launch dashboard
    python paper/audit/cell_review_app.py --export   # regenerate derived files
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

QUEUE_JSON = AUDIT_DIR / "cell_review_queue.json"
QUEUE_CSV = AUDIT_DIR / "cell_review_queue.csv"
PROGRESS_JSON = AUDIT_DIR / "cell_review_progress.json"
DASHBOARD = AUDIT_DIR / "cell_review_dashboard.html"
SUMMARY_MD = AUDIT_DIR / "cell_review_summary.md"
SUMMARY_TEX = TABLES_DIR / "cell_audit_summary.tex"

HUMAN_COLUMNS = ["human_gold_ok", "human_judge_ok", "human_notes"]
BEHAVIOR_ORDER = ["context_follow", "both_claims", "memory_override", "conflict_awareness", "refusal_or_insufficient", "unrelated_or_failed", "UNLABELED"]
CELL_ORDER = ["TP", "FP", "FN", "TN"]

_lock = threading.Lock()


def load_queue():
    return json.loads(QUEUE_JSON.read_text(encoding="utf-8"))["cases"]


def load_progress():
    if PROGRESS_JSON.exists():
        try:
            return json.loads(PROGRESS_JSON.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def save_progress(p):
    PROGRESS_JSON.write_text(json.dumps(p, indent=2, sort_keys=True), encoding="utf-8")


def is_done(labels):
    labels = labels or {}
    return bool(labels.get("human_gold_ok")) and bool(labels.get("human_judge_ok"))


def sync_csv(progress):
    if not QUEUE_CSV.exists():
        return
    with QUEUE_CSV.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        fields = reader.fieldnames or []
        rows = list(reader)
    for r in rows:
        lab = progress.get(r.get("case_id"), {})
        for k in HUMAN_COLUMNS:
            if k in fields:
                r[k] = lab.get(k, "")
    with QUEUE_CSV.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def compute_summary(cases, progress):
    groups = {}
    for c in cases:
        g = c["group"]
        groups.setdefault(g, {"behavior": c["behavior"], "cell": c["cell"], "total": c.get("group_total"), "cases": []})
        groups[g]["cases"].append(c)
    rows = []
    for beh in BEHAVIOR_ORDER:
        for cell in CELL_ORDER:
            g = f"{beh}/{cell}"
            if g not in groups:
                continue
            members = groups[g]["cases"]
            reviewed = [c for c in members if is_done(progress.get(c["case_id"], {}))]
            def cnt(field, val):
                return sum(1 for c in reviewed if (progress.get(c["case_id"], {}) or {}).get(field) == val)
            valid = sum(1 for c in reviewed if (progress.get(c["case_id"], {}) or {}).get("human_gold_ok") == "yes"
                        and (progress.get(c["case_id"], {}) or {}).get("human_judge_ok") == "yes")
            rows.append({
                "behavior": beh, "cell": cell,
                "sampled": len(members), "population": groups[g]["total"], "reviewed": len(reviewed),
                "gold_yes": cnt("human_gold_ok", "yes"), "gold_no": cnt("human_gold_ok", "no"), "gold_unclear": cnt("human_gold_ok", "unclear"),
                "judge_yes": cnt("human_judge_ok", "yes"), "judge_no": cnt("human_judge_ok", "no"), "judge_unclear": cnt("human_judge_ok", "unclear"),
                "cell_valid": valid,
            })
    return {"rows": rows}


def write_summary(cases, progress):
    s = compute_summary(cases, progress)
    total = sum(r["sampled"] for r in s["rows"])
    rev = sum(r["reviewed"] for r in s["rows"])
    L = ["# Behavior x cell review summary", "",
         "_Targeted author audit. Each case: is the gold label right (gold_ok) and did the judge call it right vs the source (judge_ok)._", "",
         f"Progress: **{rev} / {total}** cases reviewed.", "",
         "| Behavior | Cell | sampled / pop | reviewed | gold ok (y/n/?) | judge ok (y/n/?) | cell valid |",
         "|---|---|---|---|---|---|---|"]
    for r in s["rows"]:
        L.append(f"| {r['behavior']} | {r['cell']} | {r['sampled']}/{r['population']} | {r['reviewed']} | "
                 f"{r['gold_yes']}/{r['gold_no']}/{r['gold_unclear']} | {r['judge_yes']}/{r['judge_no']}/{r['judge_unclear']} | {r['cell_valid']} |")
    L.append("")
    L.append("**cell valid** = gold_ok yes AND judge_ok yes (the verdict is correctly placed in this cell). "
             "Derivations: FP with judge_ok=yes -> alternate/real error the target-gold missed; FP with judge_ok=no -> genuine false alarm; "
             "FP/FN with gold_ok=no -> gold mislabel; TN with judge_ok=no -> judge missed a real error.")
    SUMMARY_MD.write_text("\n".join(L) + "\n", encoding="utf-8")

    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    T = ["% Auto-generated by paper/audit/cell_review_app.py -- do not edit by hand.",
         r"\begin{table}[t]", r"\centering", r"\small", r"\begin{tabular}{ll rr rr r}", r"\toprule",
         r"Behavior & Cell & samp/pop & rev & gold ok (y/n/?) & judge ok (y/n/?) & valid \\", r"\midrule"]
    for r in s["rows"]:
        T.append(f"{r['behavior'].replace('_',chr(92)+'_')} & {r['cell']} & {r['sampled']}/{r['population']} & {r['reviewed']} & "
                 f"{r['gold_yes']}/{r['gold_no']}/{r['gold_unclear']} & {r['judge_yes']}/{r['judge_no']}/{r['judge_unclear']} & {r['cell_valid']} \\\\")
    T += [r"\bottomrule", r"\end{tabular}",
          r"\caption{Targeted author audit of the behavior$\times$cell grid. Per group: cases sampled / cell population, "
          r"number reviewed, and whether the human found the gold label correct (gold ok) and the judge's flag decision "
          r"correct against the source (judge ok). \emph{valid} counts cases where both hold.}",
          r"\label{tab:cell-audit}", r"\end{table}"]
    SUMMARY_TEX.write_text("\n".join(T) + "\n", encoding="utf-8")
    return s


def regenerate_all():
    cases = load_queue()
    progress = load_progress()
    sync_csv(progress)
    s = write_summary(cases, progress)
    return cases, progress, s


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
                cases = load_queue(); progress = load_progress()
                return self._send(200, {"cases": cases, "progress": progress, "summary": compute_summary(cases, progress)})
        if self.path == "/api/summary":
            with _lock:
                return self._send(200, compute_summary(load_queue(), load_progress()))
        return self._send(404, {"error": "not found"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            return self._send(400, {"error": "bad json"})
        if self.path == "/api/save":
            cid = data.get("case_id")
            labels = data.get("labels") or {}
            clean = {k: labels.get(k, "") for k in HUMAN_COLUMNS}
            clean["updated_at"] = int(time.time())
            with _lock:
                progress = load_progress()
                progress[cid] = clean
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
        raise SystemExit("Queue not found. Run: python paper/audit/build_cell_review_queue.py")
    if PROGRESS_JSON.exists():
        bak = AUDIT_DIR / ("cell_review_progress.backup-" + time.strftime("%Y%m%d-%H%M%S") + ".json")
        bak.write_text(PROGRESS_JSON.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"  backup:   {bak.relative_to(ROOT)}")
    regenerate_all()
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/"
    print(f"Cell-review dashboard → {url}")
    print(f"  progress: {PROGRESS_JSON.relative_to(ROOT)} (auto-saved)")
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
    ap.add_argument("--port", type=int, default=8766)
    ap.add_argument("--export", action="store_true")
    args = ap.parse_args()
    if args.export:
        cases, progress, s = regenerate_all()
        rev = sum(r["reviewed"] for r in s["rows"])
        print(f"Exported. Reviewed {rev}/{len(cases)}. Wrote summary + tex + synced CSV.")
        return
    serve(args.port)


if __name__ == "__main__":
    main()
