"""Step 3: validate the perturbation with 5 gates + plausibility.

LLM audit + deterministic leakage re-check (the latter overrides the LLM).
"""
from __future__ import annotations

from contextlib import nullcontext

from ..prompts import VALIDATE_SCHEMA, VALIDATE_SYSTEM, VALIDATE_USER
from ..providers.azure_openai import ProviderIncomplete
from ..schemas import CoreRecord, Validation
from .base import Step, StepContext
from .perturb_step import _normalize_for_leakage


def _format_passages(passages, ids: set[int]) -> str:
    parts = []
    for p in passages:
        if p.passage_id in ids:
            parts.append(f"[{p.passage_id}] {p.text}")
    return "\n\n".join(parts)


class ValidateStep(Step):
    name = "validate"
    requires_llm = True

    def run_record(self, record: CoreRecord, ctx: StepContext) -> CoreRecord | None:
        if (
            record.original_value is None
            or record.perturbed_value is None
            or not record.all_grounding_perturbed
        ):
            record.pipeline_state["validate"] = "skipped:no_perturbation"
            return record
        if ctx.provider is None:
            raise RuntimeError("validate step requires --model")

        ov_norm = _normalize_for_leakage(record.original_value)
        deterministic_leakage = [
            p.passage_id
            for p in record.all_grounding_perturbed
            if ov_norm and ov_norm in _normalize_for_leakage(p.text)
        ]

        target_ids = set(record.modified_passage_ids)
        user = VALIDATE_USER.format(
            question=record.question,
            atomic_claim_original=record.atomic_claim_original or "",
            atomic_claim_perturbed=record.atomic_claim_perturbed or "",
            original_value=record.original_value,
            perturbed_value=record.perturbed_value,
            original_passages=_format_passages(record.all_grounding_original, target_ids),
            perturbed_passages=_format_passages(record.all_grounding_perturbed, target_ids),
        )

        trace_cm = (
            ctx.trace.call(
                core_id=record.core_id,
                provider=ctx.provider.name,
                model=ctx.provider.model,
                system_prompt=VALIDATE_SYSTEM,
                user_prompt=user,
            )
            if ctx.trace
            else nullcontext({})
        )

        try:
            with trace_cm as slot:
                resp = ctx.provider.complete_json(
                    system=VALIDATE_SYSTEM,
                    user=user,
                    schema_hint=VALIDATE_SCHEMA,
                    max_tokens=2048,
                )
                slot["raw_response"] = resp.text
                slot["parsed_output"] = resp.parsed_json
                slot["input_tokens"] = resp.input_tokens
                slot["output_tokens"] = resp.output_tokens
                parsed = resp.parsed_json
        except ProviderIncomplete as exc:
            record.pipeline_state["validate"] = f"failed:llm_{exc.reason}"
            return record

        v = Validation()
        if parsed:
            v.type_valid = bool(parsed.get("type_valid"))
            v.answer_causal = bool(parsed.get("answer_causal"))
            v.global_context_consistent = bool(parsed.get("global_context_consistent"))
            v.no_original_answer_leakage = bool(parsed.get("no_original_answer_leakage"))
            v.original_contradicts_perturbed = bool(parsed.get("original_contradicts_perturbed"))
            v.plausibility = parsed.get("plausibility")
            reasons = parsed.get("rejection_reasons") or []
            v.rejection_reasons = [str(r) for r in reasons if r]

        if deterministic_leakage:
            v.no_original_answer_leakage = False
            v.rejection_reasons.append(f"deterministic_leakage:{deterministic_leakage}")

        record.validation = v
        record.pipeline_state["validate"] = "ok" if v.passes else "failed:validation"
        return record
