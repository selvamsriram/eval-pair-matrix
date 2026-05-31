"""Frozen curated experimental datasets.

A built exp dataset is a CoreRecord JSONL file living under data/exp/<name>.jsonl,
with a sidecar <name>.manifest.json recording the exact provenance:

  - source raw JSONL
  - seed
  - row count of source
  - count passing gates
  - selected_n (records written)
  - strata distribution actually realized
  - selected sample_ids (full list, for reproducibility / audit)

Records are written in the order produced by the stratified round-robin selection,
so any contiguous slice (offset:take) preserves approximate stratum balance.
"""
from __future__ import annotations

import time
from pathlib import Path

import orjson

from .config import PATHS
from .io import read_jsonl, write_jsonl
from .schemas import CoreRecord
from .steps.filter_step import (
    _passes_gates,
    _stratify,
    _to_core,
)


def _exp_dir() -> Path:
    d = PATHS.data / "exp"
    d.mkdir(parents=True, exist_ok=True)
    return d


def exp_path(name: str) -> Path:
    return _exp_dir() / f"{name}.jsonl"


def manifest_path(name: str) -> Path:
    return _exp_dir() / f"{name}.manifest.json"


def list_exp() -> list[dict]:
    """All exp datasets on disk, newest first."""
    out: list[dict] = []
    for p in sorted(_exp_dir().glob("*.jsonl"), key=lambda x: x.stat().st_mtime, reverse=True):
        name = p.stem
        mp = manifest_path(name)
        manifest = orjson.loads(mp.read_bytes()) if mp.exists() else {}
        n = sum(1 for _ in read_jsonl(p))
        out.append({"name": name, "path": str(p), "n": n, "manifest": manifest})
    return out


def combine_exp(
    *,
    sources: list[Path],
    name: str,
    order: str = "round-robin",
    seed: int = 17,
    overwrite: bool = False,
) -> tuple[Path, dict]:
    """Combine multiple CoreRecord JSONL files into one frozen exp dataset.

    `order`:
      - "round-robin" — interleave one record from each source in turn.
        With equal-sized sources this produces a stratified-by-source ordering
        where any contiguous slice draws evenly from each source.
      - "sequential"  — concatenate sources in the order given.
      - "shuffle"     — random shuffle of the union (seeded).

    Records are written verbatim (full CoreRecord payload), so all upstream
    fields including `generators`, `validation`, `all_grounding_perturbed`
    flow through unchanged.
    """
    out = exp_path(name)
    mout = manifest_path(name)
    if out.exists() and not overwrite:
        raise FileExistsError(
            f"{out} already exists. Pass --overwrite to replace."
        )
    for s in sources:
        if not s.exists():
            raise FileNotFoundError(f"source not found: {s}")

    src_records: list[list[dict]] = [list(read_jsonl(s)) for s in sources]

    if order == "round-robin":
        max_len = max((len(s) for s in src_records), default=0)
        combined: list[dict] = []
        for i in range(max_len):
            for src in src_records:
                if i < len(src):
                    combined.append(src[i])
    elif order == "sequential":
        combined = [r for src in src_records for r in src]
    elif order == "shuffle":
        import random as _rnd
        combined = [r for src in src_records for r in src]
        _rnd.Random(seed).shuffle(combined)
    else:
        raise ValueError(f"Unknown order: {order!r}")

    write_jsonl(out, combined)

    manifest = {
        "name": name,
        "created_at": int(time.time()),
        "kind": "combined",
        "order": order,
        "seed": seed if order == "shuffle" else None,
        "sources": [str(s) for s in sources],
        "source_counts": [len(s) for s in src_records],
        "total": len(combined),
        "provider_breakdown_perturb": _provider_breakdown(combined, "perturb"),
        "provider_breakdown_validate": _provider_breakdown(combined, "validate"),
        "validation_pass_rate": _validation_pass_rate(combined),
    }
    mout.write_bytes(orjson.dumps(manifest, option=orjson.OPT_INDENT_2))
    return out, manifest


def _provider_breakdown(records: list[dict], step: str) -> dict[str, int]:
    """Count records by provider stamped on a particular step (perturb/validate)."""
    from collections import Counter
    c: Counter = Counter()
    for r in records:
        prov = ((r.get("generators") or {}).get(step) or {}).get("provider", "unknown")
        c[prov] += 1
    return dict(c)


def _validation_pass_rate(records: list[dict]) -> dict:
    """Simple pass/fail count by reading pipeline_state.validate."""
    passed = total = 0
    for r in records:
        st = (r.get("pipeline_state") or {}).get("validate", "")
        if not st:
            continue
        total += 1
        if st == "ok":
            passed += 1
    return {"passed": passed, "total": total}


def build_exp(
    *,
    source: Path,
    name: str,
    n: int,
    seed: int = 17,
    prefer_cited: bool = True,
    overwrite: bool = False,
) -> tuple[Path, dict]:
    """Build (or rebuild) a frozen curated dataset. Returns (path, manifest)."""
    out = exp_path(name)
    mout = manifest_path(name)
    if out.exists() and not overwrite:
        raise FileExistsError(
            f"{out} already exists. Pass --overwrite to replace, "
            f"or pick a different --name to keep both."
        )
    if not source.exists():
        raise FileNotFoundError(f"source not found: {source}")

    raw_count = 0
    passing: list[CoreRecord] = []
    for raw in read_jsonl(source):
        raw_count += 1
        if _passes_gates(raw):
            passing.append(_to_core(raw))

    # Stratification: prefer cited examples, backfill with the rest.
    if prefer_cited:
        preferred, fallback = [], []
        for r in passing:
            has_cited_answer = any(
                (p.evidence_correct or "").upper() == "ANSWER-THE-QUESTION"
                and (p.evidence_cited or "").upper() == "YES"
                for p in r.all_grounding_original
            )
            (preferred if has_cited_answer else fallback).append(r)
        selected = _stratify(preferred, n, seed)
        if len(selected) < n:
            selected.extend(_stratify(fallback, n - len(selected), seed + 1))
    else:
        selected = _stratify(passing, n, seed)

    # Realized stratum counts
    strata: dict[str, int] = {}
    for r in selected:
        key = (
            f"{r.question_popularity or '?'}/"
            f"{r.question_complexity or '?'}/"
            f"{r.question_category or '?'}"
        )
        strata[key] = strata.get(key, 0) + 1

    write_jsonl(out, selected)
    manifest = {
        "name": name,
        "created_at": int(time.time()),
        "source": str(source),
        "raw_row_count": raw_count,
        "passing_gates": len(passing),
        "requested_n": n,
        "selected_n": len(selected),
        "seed": seed,
        "prefer_cited": prefer_cited,
        "strata_counts": strata,
        "sample_ids": [r.garage_sample_id for r in selected],
    }
    mout.write_bytes(orjson.dumps(manifest, option=orjson.OPT_INDENT_2))
    return out, manifest
