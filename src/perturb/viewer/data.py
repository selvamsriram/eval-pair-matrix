"""Read-side utilities for the trace viewer.

Records: each step writes a full CoreRecord-shaped row to its own JSONL.
Downstream steps preserve upstream fields, so the latest step that has a given
core_id holds the most complete view of that record.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import orjson

from ..config import PATHS
from ..io import read_jsonl
from ..run import STEP_ORDER, Run, list_runs, open_run


@dataclass(frozen=True)
class RecordSummary:
    core_id: str
    question: str
    last_step: str
    last_step_status: str
    validation_passes: bool | None
    perturbation_type: str | None
    generation_count: int
    latest_generator: str | None
    latest_generation_mode: str | None
    latest_behavior_label: str | None


@dataclass(frozen=True)
class TraceSummary:
    event_id: str
    step: str
    model: str
    provider: str
    latency_ms: int | None
    input_tokens: int | None
    output_tokens: int | None
    has_error: bool
    started_at: float


# ---------- Run discovery ----------


def latest_run() -> Run | None:
    runs = list_runs()
    return runs[0] if runs else None


def all_runs() -> list[dict]:
    out = []
    for r in list_runs():
        manifest = r.read_manifest()
        steps_present = [s for s in STEP_ORDER if _visible_step_path(r, s) is not None]
        out.append(
            {
                "run_id": r.run_id,
                "dir": str(r.dir),
                "steps_present": steps_present,
                "manifest": manifest,
            }
        )
    return out


# ---------- Records ----------


def _tmp_path(path: Path) -> Path:
    return path.with_suffix(path.suffix + ".tmp")


def _visible_step_path(run: Run, step: str) -> Path | None:
    """Finalized JSONL if present, otherwise the in-progress tmp file.

    Pipeline writes are atomic, so active runs only have `*.jsonl.tmp` until the
    step completes. The viewer is read-only/audit-only, so it can safely show
    complete rows already flushed to the tmp file.
    """
    path = run.step_path(step)
    if path.exists():
        return path
    tmp = _tmp_path(path)
    return tmp if tmp.exists() else None


def _read_records(path: Path) -> dict[str, dict]:
    """Return core_id → record dict."""
    if not path.exists():
        return {}
    out: dict[str, dict] = {}
    with path.open("rb") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                raw = orjson.loads(line)
            except orjson.JSONDecodeError:
                # A live tmp file may end with a partial line while the writer
                # is between writes. Ignore that tail; the next refresh will
                # pick it up once complete.
                break
            cid = raw.get("core_id")
            if isinstance(cid, str):
                out[cid] = raw
    return out


def merged_records(run: Run) -> dict[str, dict]:
    """For every core_id ever produced in this run, return the record from the latest
    step that contains it. Newer step files override older ones."""
    merged: dict[str, dict] = {}
    for step_name in STEP_ORDER:
        path = _visible_step_path(run, step_name)
        if path is None:
            continue
        for cid, rec in _read_records(path).items():
            merged[cid] = rec
    return merged


def list_record_summaries(run: Run) -> list[RecordSummary]:
    records = merged_records(run)
    summaries: list[RecordSummary] = []
    for cid, rec in records.items():
        state: dict[str, str] = rec.get("pipeline_state") or {}
        # Walk STEP_ORDER backward to find the most-recent step touched.
        last_step = "filter"
        last_status = ""
        for s in STEP_ORDER:
            if s in state:
                last_step = s
                last_status = state[s]
        validation = rec.get("validation") or {}
        passes: bool | None = None
        if any(v is not None for v in validation.values() if isinstance(v, (bool, type(None)))):
            gates = [
                validation.get(k)
                for k in (
                    "type_valid",
                    "answer_causal",
                    "global_context_consistent",
                    "no_original_answer_leakage",
                    "original_contradicts_perturbed",
                )
            ]
            passes = all(g is True for g in gates) if all(g is not None for g in gates) else None
        generator_outputs = rec.get("generator_outputs") or []
        latest_generation = generator_outputs[-1] if generator_outputs else {}
        latest_provider = latest_generation.get("generator_provider")
        latest_model = latest_generation.get("generator_model")
        latest_generator = (
            f"{latest_provider}/{latest_model}"
            if latest_provider and latest_model
            else latest_provider or latest_model
        )
        summaries.append(
            RecordSummary(
                core_id=cid,
                question=rec.get("question", ""),
                last_step=last_step,
                last_step_status=last_status,
                validation_passes=passes,
                perturbation_type=rec.get("perturbation_type"),
                generation_count=len(generator_outputs),
                latest_generator=latest_generator,
                latest_generation_mode=latest_generation.get("mode"),
                latest_behavior_label=latest_generation.get("behavior_label"),
            )
        )
    # Stable order: by core_id so the UI doesn't jump around.
    summaries.sort(key=lambda s: s.core_id)
    return summaries


def get_record(run: Run, core_id: str) -> dict | None:
    return merged_records(run).get(core_id)


# ---------- Trace events ----------


def trace_events_for(run: Run, core_id: str) -> list[dict]:
    """All LLM trace events for one core_id across every step's trace file."""
    events: list[dict] = []
    trace_root = PATHS.traces / run.run_id
    if not trace_root.exists():
        return events
    for step_name in STEP_ORDER:
        tp = trace_root / f"{step_name}.jsonl"
        if not tp.exists():
            continue
        for raw in read_jsonl(tp):
            if raw.get("core_id") == core_id:
                events.append(raw)
    events.sort(key=lambda e: e.get("started_at", 0))
    return events


def trace_summary(run: Run, step: str, tail: int = 20) -> list[TraceSummary]:
    tp = PATHS.traces / run.run_id / f"{step}.jsonl"
    if not tp.exists():
        return []
    rows = list(read_jsonl(tp))[-tail:]
    return [
        TraceSummary(
            event_id=r.get("event_id", "")[:8],
            step=r.get("step", step),
            model=r.get("model", ""),
            provider=r.get("provider", ""),
            latency_ms=r.get("latency_ms"),
            input_tokens=r.get("input_tokens"),
            output_tokens=r.get("output_tokens"),
            has_error=bool(r.get("error")),
            started_at=r.get("started_at", 0),
        )
        for r in rows
    ]


# ---------- Diff helpers ----------


def passage_diffs(record: dict) -> list[dict]:
    """Pair each original passage with its perturbed counterpart by passage_id.

    Returns: [{passage_id, label, original_text, perturbed_text, was_modified, mod}]
    where `mod` is the matching doc_modifications entry if present.
    """
    originals: dict[int, dict] = {
        int(p["passage_id"]): p for p in (record.get("all_grounding_original") or [])
    }
    perturbed: dict[int, dict] = {
        int(p["passage_id"]): p for p in (record.get("all_grounding_perturbed") or [])
    }
    mods: dict[int, dict] = {
        int(m["passage_id"]): m for m in (record.get("doc_modifications") or [])
    }
    out = []
    for pid in sorted(originals):
        op = originals[pid]
        pp = perturbed.get(pid, op)
        out.append(
            {
                "passage_id": pid,
                "label": op.get("evidence_correct") or "UNLABELED",
                "cited": op.get("evidence_cited"),
                "original_text": op.get("text", ""),
                "perturbed_text": pp.get("text", ""),
                "was_modified": bool(pp.get("was_modified")),
                "mod": mods.get(pid),
            }
        )
    return out
