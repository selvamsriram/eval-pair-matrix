"""Step 1: filter and stratify GaRAGe.

Gates (from PROPOSAL.md Step 1):
  question_valid == True
  question_seeking == True
  question_false_premise == False
  answer_validate == True
  >= 2 grounding passages with evidence_correct == "ANSWER-THE-QUESTION"

Stratifies the sample across question_popularity x question_complexity x
question_category to avoid skew. If a stratum is under-represented we backfill
from the residual pool.
"""
from __future__ import annotations

import hashlib
import random
from collections import defaultdict
from typing import Iterable, Iterator

from ..schemas import CoreRecord, GroundingPassage
from .base import Step, StepContext

ANSWER_TAG = "ANSWER-THE-QUESTION"
MIN_ANSWER_PASSAGES = 2


def _truthy(v) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.strip().lower() in ("true", "yes", "1")
    return bool(v)


def _passes_gates(raw: dict) -> bool:
    if not _truthy(raw.get("question_valid")):
        return False
    if not _truthy(raw.get("question_seeking", True)):  # default True if absent
        return False
    if _truthy(raw.get("question_false_premise", False)):
        return False
    if "answer_validate" in raw and not _truthy(raw.get("answer_validate")):
        return False
    n_answer = _count_answer_passages(raw)
    return n_answer >= MIN_ANSWER_PASSAGES


def _count_answer_passages(raw: dict) -> int:
    """Real GaRAGe stores evidence_correct as a top-level array parallel to grounding;
    synthetic data embeds it per-passage. Support both."""
    top = raw.get("evidence_correct")
    if isinstance(top, list):
        return sum(1 for v in top if (v or "").upper() == ANSWER_TAG)
    grounding = raw.get("grounding") or []
    return sum(
        1 for p in grounding if (p.get("evidence_correct") or "").upper() == ANSWER_TAG
    )


def _passage_text(p: dict, idx: int) -> str:
    """GaRAGe stores passage text in cite_{idx+1}; if missing, take the first
    non-empty cite_* slot. Synthetic data uses a flat `text` field, also supported."""
    if isinstance(p.get("text"), str) and p["text"]:
        return p["text"]
    primary = p.get(f"cite_{idx + 1}")
    if isinstance(primary, str) and primary.strip():
        return primary
    for k, v in p.items():
        if k.startswith("cite_") and isinstance(v, str) and v.strip():
            return v
    return ""


def _evidence_at(raw: dict, key: str, idx: int, passage: dict) -> str | None:
    """Per-passage evidence label. GaRAGe puts these as top-level arrays
    parallel to `grounding`; synthetic data uses per-passage keys."""
    top = raw.get(key)
    if isinstance(top, list) and idx < len(top):
        return top[idx]
    return passage.get(key)


def _to_core(raw: dict) -> CoreRecord:
    sample_id = str(raw.get("sample_id") or raw.get("id") or raw.get("question_id") or "")
    core_id = "garage_core_" + hashlib.sha1(sample_id.encode()).hexdigest()[:12]

    grounding_raw = raw.get("grounding") or []
    grounding: list[GroundingPassage] = []
    answer_ids: list[int] = []
    for idx, p in enumerate(grounding_raw):
        passage_id = int(p.get("passage_id", idx))
        gp = GroundingPassage(
            passage_id=passage_id,
            text=_passage_text(p, idx),
            provider=p.get("provider"),
            passage_date=p.get("passage_date") or p.get("date"),
            evidence_relevant=_evidence_at(raw, "evidence_relevant", idx, p),
            evidence_correct=_evidence_at(raw, "evidence_correct", idx, p),
            evidence_cited=_evidence_at(raw, "evidence_cited", idx, p),
        )
        grounding.append(gp)
        if (gp.evidence_correct or "").upper() == ANSWER_TAG:
            answer_ids.append(passage_id)

    return CoreRecord(
        core_id=core_id,
        garage_sample_id=sample_id,
        question=raw.get("question", ""),
        question_date=raw.get("question_date"),
        question_category=raw.get("question_category"),
        question_complexity=raw.get("question_complexity"),
        question_popularity=raw.get("question_popularity"),
        question_type=raw.get("question_type"),
        answer_generate=raw.get("answer_generate", "") or raw.get("answer", ""),
        all_grounding_original=grounding,
        answer_containing_passage_ids=answer_ids,
        pipeline_state={"filter": "ok"},
    )


def _stratify(records: list[CoreRecord], n: int, seed: int) -> list[CoreRecord]:
    """Round-robin draw across (popularity, complexity, category) buckets, then backfill."""
    rng = random.Random(seed)
    buckets: dict[tuple, list[CoreRecord]] = defaultdict(list)
    for r in records:
        key = (
            r.question_popularity or "unknown",
            r.question_complexity or "unknown",
            r.question_category or "unknown",
        )
        buckets[key].append(r)
    for v in buckets.values():
        rng.shuffle(v)

    selected: list[CoreRecord] = []
    seen_ids: set[str] = set()
    keys = list(buckets.keys())
    rng.shuffle(keys)
    while len(selected) < n and any(buckets.values()):
        progressed = False
        for k in keys:
            if len(selected) >= n:
                break
            if not buckets[k]:
                continue
            cand = buckets[k].pop()
            if cand.core_id in seen_ids:
                continue
            selected.append(cand)
            seen_ids.add(cand.core_id)
            progressed = True
        if not progressed:
            break
    return selected


class FilterStep(Step):
    name = "filter"
    requires_llm = False

    def run_record(self, record: CoreRecord, ctx: StepContext) -> CoreRecord | None:
        # Not used — filter overrides run_stream because it bootstraps the pipeline.
        return record

    def run_stream(
        self, records: Iterable[dict], ctx: StepContext
    ) -> Iterator[CoreRecord]:
        # Materialize so we can peek at the first record without losing it.
        materialized = list(records)
        offset: int = int(ctx.options.get("offset") or 0)
        take: int | None = ctx.options.get("take")
        take = int(take) if take is not None else None

        # Passthrough mode: source is already CoreRecord-shaped (e.g. a frozen
        # exp dataset). Skip gates/stratify; just slice with offset/take.
        if materialized and isinstance(materialized[0], dict) and "core_id" in materialized[0]:
            end = offset + take if take is not None else len(materialized)
            for raw in materialized[offset:end]:
                rec = CoreRecord.model_validate(raw)
                rec.pipeline_state["filter"] = "ok"
                yield rec
            return

        # Build-from-raw mode: gates + normalize + stratified sample.
        target_n: int = int(ctx.options.get("n", 200))
        seed: int = int(ctx.options.get("seed", 17))
        prefer_cited: bool = bool(ctx.options.get("prefer_cited", True))

        passing: list[CoreRecord] = []
        for raw in materialized:
            if not _passes_gates(raw):
                continue
            passing.append(_to_core(raw))

        if prefer_cited:
            preferred, fallback = [], []
            for r in passing:
                has_cited_answer = any(
                    (p.evidence_correct or "").upper() == ANSWER_TAG
                    and (p.evidence_cited or "").upper() == "YES"
                    for p in r.all_grounding_original
                )
                (preferred if has_cited_answer else fallback).append(r)
            primary = _stratify(preferred, target_n, seed)
            if len(primary) < target_n:
                remaining = target_n - len(primary)
                primary.extend(_stratify(fallback, remaining, seed + 1))
            selected = primary
        else:
            selected = _stratify(passing, target_n, seed)

        # Apply slicing in build-from-raw mode too, for consistency.
        end = offset + take if take is not None else len(selected)
        for r in selected[offset:end]:
            yield r
