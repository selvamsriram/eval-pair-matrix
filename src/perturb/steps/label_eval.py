"""Step 5: LLM-driven re-evaluation of generator outputs.

For each GeneratorOutput on each CoreRecord, makes one LLM call to classify
the answer's behavior with full knowledge of the perturbation (original_value,
perturbed_value, modified passages, the generator's answer + citations).

Writes the result back as `generator_output.llm_eval` (LLMBehaviorEval),
PRESERVING the existing deterministic `behavior_label` so downstream analysis
can diff code-based vs LLM-based labels per record.

Each LLM call carries `metadata` on the trace event identifying which
generator_output it evaluated, so the existing trace infrastructure picks it
up cleanly in the viewer (Traces tab) and in any code-vs-LLM agreement audit
script.
"""
from __future__ import annotations

import time
from contextlib import nullcontext

from ..prompts import LABEL_EVAL_SCHEMA, LABEL_EVAL_SYSTEM, LABEL_EVAL_USER
from ..providers.azure_openai import ProviderIncomplete
from ..schemas import (
    BehaviorLabel,
    CoreRecord,
    GeneratorOutput,
    GroundingPassage,
    LLMBehaviorEval,
)
from .base import Step, StepContext

_LABELS: tuple[BehaviorLabel, ...] = (
    "context_follow",
    "memory_override",
    "both_claims",
    "conflict_awareness",
    "refusal_or_insufficient",
    "unrelated_or_failed",
)


def _format_modified_passages(record: CoreRecord) -> str:
    mod_ids = set(record.modified_passage_ids or [])
    parts = []
    for p in record.all_grounding_perturbed or []:
        if p.passage_id in mod_ids:
            parts.append(f"[{p.passage_id}] {p.text}")
    if not parts:
        # Fallback if modified_passage_ids missing — show first 5 perturbed passages
        parts = [f"[{p.passage_id}] {p.text}" for p in (record.all_grounding_perturbed or [])[:5]]
    return "\n\n".join(parts) if parts else "(no perturbed passages available)"


def _eval_one(
    record: CoreRecord,
    g: GeneratorOutput,
    ctx: StepContext,
) -> LLMBehaviorEval | None:
    """One LLM call per (record × generator_output)."""
    if ctx.provider is None:
        raise RuntimeError("label_eval step requires --model")

    # Build the prompt
    user = LABEL_EVAL_USER.format(
        question=record.question,
        original_value=record.original_value or "(unknown)",
        perturbed_value=record.perturbed_value or "(unknown)",
        atomic_claim_original=record.atomic_claim_original or "(none)",
        atomic_claim_perturbed=record.atomic_claim_perturbed or "(none)",
        modified_passages=_format_modified_passages(record),
        answer=(g.answer_text or "(empty)"),
        cited_passage_ids=g.cited_passage_ids or [],
        is_refusal=g.is_refusal,
    )

    trace_cm = (
        ctx.trace.call(
            core_id=record.core_id,
            provider=ctx.provider.name,
            model=ctx.provider.model,
            system_prompt=LABEL_EVAL_SYSTEM,
            user_prompt=user,
            metadata={
                "evaluator_model": ctx.provider.model,
                "evaluator_provider": ctx.provider.name,
                "evaluated_generator_model": g.generator_model,
                "evaluated_generator_provider": g.generator_provider,
                "evaluated_generator_mode": g.mode,
                "evaluated_generator_sample_id": g.sample_id,
                "deterministic_label": g.behavior_label,
            },
        )
        if ctx.trace
        else nullcontext({})
    )

    try:
        with trace_cm as slot:
            resp = ctx.provider.complete_json(
                system=LABEL_EVAL_SYSTEM,
                user=user,
                schema_hint=LABEL_EVAL_SCHEMA,
                max_tokens=1024,
            )
            slot["raw_response"] = resp.text
            slot["parsed_output"] = resp.parsed_json
            slot["input_tokens"] = resp.input_tokens
            slot["output_tokens"] = resp.output_tokens
            parsed = resp.parsed_json
    except ProviderIncomplete:
        return None  # caller marks pipeline_state with the reason

    if not parsed:
        return None

    label = parsed.get("behavior_label")
    if label not in _LABELS:
        return None

    return LLMBehaviorEval(
        evaluator_provider=ctx.provider.name,
        evaluator_model=ctx.provider.model,
        behavior_label=label,  # type: ignore[arg-type]
        entails_original_claim=bool(parsed.get("entails_original_claim")),
        entails_perturbed_claim=bool(parsed.get("entails_perturbed_claim")),
        rationale=(str(parsed.get("rationale"))[:600] if parsed.get("rationale") else None),
        confidence=parsed.get("confidence") if parsed.get("confidence") in ("high","medium","low") else None,
        run_id=ctx.run_id,
        completed_at=int(time.time()),
    )


class LabelEvalStep(Step):
    name = "label_eval"
    requires_llm = True

    def run_record(self, record: CoreRecord, ctx: StepContext) -> CoreRecord | None:
        if not record.generator_outputs:
            record.pipeline_state["label_eval"] = "skipped:no_generator_outputs"
            return record

        any_ok = any_failed = 0
        for g in record.generator_outputs:
            # Skip outputs with no answer (failed generations). Mark a synthetic eval.
            if not (g.answer_text or "").strip():
                g.llm_eval = LLMBehaviorEval(
                    evaluator_provider=ctx.provider.name if ctx.provider else "unknown",
                    evaluator_model=getattr(ctx.provider, "model", "unknown"),
                    behavior_label="unrelated_or_failed",
                    entails_original_claim=False,
                    entails_perturbed_claim=False,
                    rationale="generator produced no answer text",
                    confidence="high",
                    run_id=ctx.run_id,
                    completed_at=int(time.time()),
                )
                any_ok += 1
                continue
            ev = _eval_one(record, g, ctx)
            if ev is None:
                any_failed += 1
                continue
            g.llm_eval = ev
            any_ok += 1

        if any_ok and not any_failed:
            record.pipeline_state["label_eval"] = "ok"
        elif any_ok:
            record.pipeline_state["label_eval"] = "ok_partial"
        else:
            record.pipeline_state["label_eval"] = "failed:all_evals_failed"
        return record
