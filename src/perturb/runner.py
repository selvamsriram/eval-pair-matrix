"""Step runner. Wires a Step + provider + trace + run dir together over a JSONL stream."""
from __future__ import annotations

import time
from collections import Counter
from pathlib import Path
from typing import Callable, Iterable

from . import providers
from .io import read_jsonl, write_jsonl
from .run import Run
from .schemas import CoreRecord, StepProvenance
from .steps import STEPS, Step, StepContext
from .trace import TraceWriter

# progress_cb signature: (payload_dict, running_statuses_counter) -> None
ProgressCallback = Callable[[dict, Counter], None]


def _resolve_step(name: str) -> Step:
    cls = STEPS[name]
    return cls()


def run_step(
    *,
    run: Run,
    step_name: str,
    source: Path | None,
    model: str | None,
    options: dict,
    progress_cb: ProgressCallback | None = None,
    resume: bool = False,
) -> tuple[Path, Counter]:
    """Execute a single step. Returns (output_path, status_counter)."""
    step = _resolve_step(step_name)

    if source is None:
        source = run.input_path_for(step_name)
    if source is None:
        raise ValueError(
            f"Step '{step_name}' is the first step and needs an explicit --source."
        )
    if not source.exists():
        raise FileNotFoundError(f"Input not found: {source}")

    provider = providers.get(model) if (model and step.requires_llm) else None
    if step.requires_llm and provider is None:
        raise RuntimeError(f"Step '{step_name}' requires --model.")

    trace_path = run.trace_path(step_name)
    trace = TraceWriter(run_id=run.run_id, step=step_name, path=trace_path)

    ctx = StepContext(run_id=run.run_id, provider=provider, trace=trace, options=options)
    src_records: Iterable[dict] = read_jsonl(source)

    out_path = run.step_path(step_name)
    statuses: Counter = Counter()

    # Resume: prepend existing records to output; skip their core_ids in input.
    existing_records: list[dict] = []
    if resume and out_path.exists():
        existing_records = list(read_jsonl(out_path))
        existing_cids = {r.get("core_id") for r in existing_records if r.get("core_id")}
        if existing_cids:
            src_records = (
                r for r in src_records if r.get("core_id") not in existing_cids  # type: ignore[union-attr]
            )

    # Build the per-step stamp once. Filter (no provider) gets no stamp.
    stamp: StepProvenance | None = None
    if provider is not None:
        stamp = StepProvenance(
            provider=provider.name,
            model=getattr(provider, "model", ""),
            run_id=run.run_id,
            completed_at=int(time.time()),
        )

    def merged():
        for r in existing_records:
            yield r
        yield from _collect_with_status(
            step.run_stream(src_records, ctx), statuses, step_name, progress_cb, stamp
        )

    n = write_jsonl(out_path, merged())
    step.finalize(ctx)

    manifest_step = {
        "input": str(source),
        "output": str(out_path),
        "records_in": _count(source),
        "records_out": n,
        "resumed_existing": len(existing_records),
        "provider": provider.name if provider else None,
        "model_id": getattr(provider, "model", None) if provider else None,
        "options": options,
        "status_counts": dict(statuses),
    }
    run.update_manifest(**{f"step_{step_name}": manifest_step})
    return out_path, statuses


def _collect_with_status(
    stream,
    statuses: Counter,
    step_name: str,
    progress_cb: ProgressCallback | None = None,
    stamp: StepProvenance | None = None,
):
    for rec in stream:
        if isinstance(rec, CoreRecord):
            statuses[rec.pipeline_state.get(step_name, "unset")] += 1
            # Auto-stamp who/what produced this step's contribution (last-writer-wins).
            if stamp is not None:
                rec.generators[step_name] = stamp
            payload = rec.model_dump(mode="json")
        else:
            payload = rec
        if progress_cb is not None:
            try:
                progress_cb(payload, statuses)
            except Exception:  # noqa: BLE001 — UI failure must not kill the run
                pass
        yield payload


def _count(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("rb") as f:
        return sum(1 for line in f if line.strip())
