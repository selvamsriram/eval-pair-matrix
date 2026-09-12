#!/usr/bin/env python3
"""Summarize recorded usage for the paper's nine production judge runs.

Reads the run inventory, portable usage ledger, and saved verdicts. Pass
--raw-traces to independently check the original local traces. Makes no model
calls and writes JSON to stdout. Both input modes produce the same report.
"""

from collections import defaultdict
import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FIELDS = ("calls", "verdicts", "errors", "input_tokens", "output_tokens",
          "missing_input_usage", "missing_output_usage", "sum_call_ms")


def rows(path):
    with path.open() as stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)


def summarize(raw_traces=False):
    inventory_path = ROOT / "paper/audit/paired_audit_report.json"
    inventory = json.loads(inventory_path.read_text())
    names = {model: name for name, model in inventory["meta"]["provider_models"].items()}
    paths = sorted(p for p in inventory["files"] if p.endswith("/06_judge.jsonl"))
    if len(paths) != 9:
        raise ValueError(f"Expected the nine production judge runs, found {len(paths)}")
    ledger_by_run = defaultdict(list)
    provenance = {}
    if not raw_traces:
        ledger_path = ROOT / "paper/audit/judge_usage.jsonl"
        manifest = json.loads((ROOT / "paper/audit/judge_usage_manifest.json").read_text())
        if hashlib.sha256(ledger_path.read_bytes()).hexdigest() != manifest["ledger_sha256"]:
            raise ValueError("Portable usage ledger differs from its manifest")
        provenance = manifest["trace_sha256"]
        for event in rows(ledger_path):
            ledger_by_run[event["run_id"]].append(event)
        if set(ledger_by_run) != {Path(p).parent.name for p in paths}:
            raise ValueError("Portable ledger does not cover exactly the nine judge runs")
    runs = []
    by_judge = defaultdict(lambda: {field: 0 for field in FIELDS})
    event_ids = set()
    for relative_path in paths:
        verdict_path = ROOT / relative_path
        run_id = verdict_path.parent.name
        trace_path = ROOT / "data/traces" / run_id / "judge.jsonl"
        events = list(rows(trace_path)) if raw_traces else ledger_by_run[run_id]
        pairs = {(e["model"], e["metadata"]["generator_model"]) for e in events}
        if len(pairs) != 1:
            raise ValueError(f"Expected one judge/generator pair in {run_id}")
        model, generator = pairs.pop()
        count = {field: 0 for field in FIELDS}
        for event in events:
            if event["event_id"] in event_ids or event["step"] != "judge":
                raise ValueError(f"Unexpected or duplicate event in {run_id}")
            event_ids.add(event["event_id"])
            count["calls"] += 1
            count["errors"] += bool(event.get("error"))
            count["sum_call_ms"] += event["latency_ms"]
            for field in ("input_tokens", "output_tokens"):
                value = event.get(field)
                if value is None:
                    count[f"missing_{field.split('_')[0]}_usage"] += 1
                else:
                    count[field] += value
        for record in rows(verdict_path):
            for verdict in record.get("judge_verdicts") or []:
                if (verdict["judge_model"], verdict["generator_model"]) != (model, generator):
                    raise ValueError(f"Unexpected saved verdict in {run_id}")
                count["verdicts"] += 1
        if count["calls"] != count["verdicts"] + count["errors"]:
            raise ValueError(f"Trace/verdict counts differ in {run_id}; inspect before reporting")
        for field in FIELDS:
            by_judge[names[model]][field] += count[field]
        runs.append({"run_id": run_id, "judge": names[model],
                     "generator": names[generator], **count,
                     "trace": str(trace_path.relative_to(ROOT)),
                     "trace_sha256": (hashlib.sha256(trace_path.read_bytes()).hexdigest()
                                      if raw_traces else provenance[run_id]),
                     "verdicts_path": relative_path,
                     "verdicts_sha256": hashlib.sha256(verdict_path.read_bytes()).hexdigest()})
    total = {field: sum(row[field] for row in runs) for field in FIELDS}
    if total["verdicts"] != inventory["counts"]["total_verdicts"]:
        raise ValueError("Saved verdict total differs from the paper's analysis inventory")
    for row in [*runs, *by_judge.values(), total]:
        row["sum_call_hours"] = row["sum_call_ms"] / 3_600_000
    return {
        "scope": "Nine production judge runs over the full 300-record pool; judging only.",
        "inventory": str(inventory_path.relative_to(ROOT)),
        "definitions": {
            "calls": "Application-level trace events, including failed calls; internal provider retries are not separately counted.",
            "tokens": "Recorded usage; missing values are counted separately, not imputed. Failed-call/retry usage and Gemini thinking tokens are not fully recorded.",
            "sum_call_hours": "Sum of latency_ms across all trace events, including errors; not wall-clock runtime.",
        },
        "runs": runs, "by_judge": dict(by_judge), "total": total,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-traces", action="store_true")
    args = parser.parse_args()
    print(json.dumps(summarize(args.raw_traces), indent=2))
