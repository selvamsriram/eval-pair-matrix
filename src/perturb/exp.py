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

import random
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


def build_balanced_exp(
    *,
    sources: list[Path],
    fill_source: Path | None,
    name: str,
    target: int = 300,
    seed: int = 17,
    overwrite: bool = False,
) -> tuple[Path, dict]:
    """Multi-source balanced builder for the 3provider_300-style exp set.

    - One record per question (core_id).
    - Prefer validation.passes==True records.
    - Provider distribution is the primary balance objective (target ≈ N/k per
      provider, capped at each provider's max validated count and slack
      redistributed to others).
    - Perturbation type is a secondary objective: when multiple providers
      validated the same question, pick the one whose (provider, type) bucket
      is most under-target.
    - If chosen_count < target after the validated pass, fill the gap from
      `fill_source` using its UNCHOSEN questions (validated or unvalidated).
    """
    out = exp_path(name)
    mout = manifest_path(name)
    if out.exists() and not overwrite:
        raise FileExistsError(f"{out} already exists. Pass --overwrite to replace.")
    for s in sources:
        if not s.exists():
            raise FileNotFoundError(f"source not found: {s}")

    # ---------- Load all sources ----------
    # provider_key derived from generators.perturb.provider on each record;
    # falls back to filename stem if missing.
    per_provider: dict[str, dict[str, dict]] = {}  # provider -> core_id -> record
    src_path_of_provider: dict[str, str] = {}
    for s in sources:
        for raw in read_jsonl(s):
            prov = (
                (raw.get("generators") or {}).get("perturb", {}).get("provider")
                or s.parent.name
            )
            per_provider.setdefault(prov, {})[raw["core_id"]] = raw
            src_path_of_provider[prov] = str(s)

    providers_in_order = list(per_provider.keys())
    all_cids = set().union(*[set(d.keys()) for d in per_provider.values()])

    # validated[provider] = set of core_ids that provider validated cleanly
    validated: dict[str, set[str]] = {}
    for prov, recs in per_provider.items():
        validated[prov] = {
            cid for cid, r in recs.items()
            if (r.get("validation") or {}).get("type_valid") is True
            and (r.get("validation") or {}).get("answer_causal") is True
            and (r.get("validation") or {}).get("global_context_consistent") is True
            and (r.get("validation") or {}).get("no_original_answer_leakage") is True
            and (r.get("validation") or {}).get("original_contradicts_perturbed") is True
        }

    max_count = {p: len(validated[p]) for p in providers_in_order}

    # ---------- Phase 1: capacity shaping (equal-as-possible) ----------
    n_p = len(providers_in_order)
    base_target = target // n_p
    targets = {p: min(base_target, max_count[p]) for p in providers_in_order}
    slack = target - sum(targets.values())
    # Redistribute slack proportional to headroom (max_count - current target)
    while slack > 0:
        headrooms = {p: max_count[p] - targets[p] for p in providers_in_order}
        if all(h <= 0 for h in headrooms.values()):
            break  # everyone capped — we'll fall through to gap fill
        # Give one to whoever has the most headroom (then re-evaluate)
        best = max(providers_in_order, key=lambda p: headrooms[p])
        if headrooms[best] <= 0:
            break
        targets[best] += 1
        slack -= 1

    # ---------- Phase 2: forced single-validator assignments ----------
    rng = random.Random(seed)
    chosen: dict[str, dict] = {}  # core_id -> chosen record
    chosen_provider: dict[str, str] = {}  # core_id -> provider name
    counts: dict[str, int] = {p: 0 for p in providers_in_order}
    type_counts: dict[str, dict[str, int]] = {p: {} for p in providers_in_order}

    def _take(cid: str, prov: str) -> None:
        rec = per_provider[prov][cid]
        chosen[cid] = rec
        chosen_provider[cid] = prov
        counts[prov] += 1
        t = rec.get("perturbation_type") or "unknown"
        type_counts[prov][t] = type_counts[prov].get(t, 0) + 1

    # For each question, which providers validated it
    validators_of: dict[str, list[str]] = {}
    for cid in all_cids:
        vs = [p for p in providers_in_order if cid in validated[p]]
        if vs:
            validators_of[cid] = vs

    # Single-validator questions: assign now (no choice)
    for cid, vs in list(validators_of.items()):
        if len(vs) == 1 and counts[vs[0]] < targets[vs[0]]:
            _take(cid, vs[0])

    # ---------- Phase 3: greedy balanced multi-validator ----------
    multi = [cid for cid, vs in validators_of.items() if len(vs) > 1 and cid not in chosen]
    # Sort: scarcest first (fewest validators), then by stable tiebreak
    multi.sort(key=lambda c: (len(validators_of[c]), c))

    def _score(prov: str, ptype: str) -> float:
        provider_deficit = targets[prov] - counts[prov]
        if provider_deficit <= 0:
            return float("-inf")  # provider is full
        type_target = max(1, targets[prov] // 10)
        type_deficit = max(0, type_target - type_counts[prov].get(ptype, 0))
        # provider deficit dominates; type acts as tiebreak; tiny random nudge for stable shuffle
        return provider_deficit * 100.0 + type_deficit + rng.random()

    for cid in multi:
        candidate_provs = validators_of[cid]
        best = None
        best_score = float("-inf")
        for p in candidate_provs:
            rec = per_provider[p][cid]
            ptype = rec.get("perturbation_type") or "unknown"
            s = _score(p, ptype)
            if s > best_score:
                best_score = s
                best = p
        if best is not None and counts[best] < targets[best]:
            _take(cid, best)

    validated_chosen = len(chosen)

    # ---------- Phase 4: gap fill from fill_source ----------
    gap_filled = 0
    excluded: list[str] = []
    if len(chosen) < target and fill_source is not None:
        fill_records = list(read_jsonl(fill_source))
        # Identify fill provider name from records (fall back to path stem)
        fill_prov = None
        for r in fill_records:
            fill_prov = (r.get("generators") or {}).get("perturb", {}).get("provider")
            if fill_prov:
                break
        fill_prov = fill_prov or fill_source.parent.name

        fill_by_cid: dict[str, dict] = {}
        for r in fill_records:
            cid = r.get("core_id")
            # Only consider records that actually have a perturbation produced
            if cid and r.get("all_grounding_perturbed"):
                fill_by_cid[cid] = r

        for cid, r in fill_by_cid.items():
            if len(chosen) >= target:
                break
            if cid in chosen:
                continue
            chosen[cid] = r
            chosen_provider[cid] = fill_prov
            counts[fill_prov] = counts.get(fill_prov, 0) + 1
            t = r.get("perturbation_type") or "unknown"
            type_counts.setdefault(fill_prov, {})
            type_counts[fill_prov][t] = type_counts[fill_prov].get(t, 0) + 1
            gap_filled += 1

    # Questions excluded (nobody had a perturbation)
    excluded = sorted(all_cids - set(chosen.keys()))

    # ---------- Write output ----------
    # Preserve a stable, useful order: by core_id (matches the rest of the system)
    final = [chosen[cid] for cid in sorted(chosen.keys())]
    write_jsonl(out, final)

    manifest = {
        "name": name,
        "created_at": int(time.time()),
        "kind": "balanced_multisource",
        "seed": seed,
        "sources": [str(s) for s in sources],
        "fill_source": str(fill_source) if fill_source else None,
        "target_total": target,
        "actual_total": len(final),
        "provider_max_capacity": max_count,
        "provider_targets": targets,
        "provider_actuals": {p: counts.get(p, 0) for p in set(list(providers_in_order) + list(counts.keys()))},
        "validated_chosen": validated_chosen,
        "gap_filled": gap_filled,
        "single_validator_questions": sum(1 for vs in validators_of.values() if len(vs) == 1),
        "multi_validator_questions": sum(1 for vs in validators_of.values() if len(vs) > 1),
        "type_distribution_per_provider": type_counts,
        "excluded_questions_count": len(excluded),
        "excluded_questions": excluded[:50],  # cap printout in manifest
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
