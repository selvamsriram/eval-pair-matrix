"""Step 4: generate RAG answers from perturbed (or original / closed-book) grounding.

For each record, runs N generator models. Each call produces one GeneratorOutput
appended to record.generator_outputs. Behavior labels are computed inline by
deterministic string matching against original_value / perturbed_value (no
extra LLM call).

This step ignores ctx.provider (the runner's single-model assumption) and
manages its own provider list from ctx.options["generators"]. Pipeline `--model`
is ignored if --generators is set; if only --model is set, that single model
is used.
"""
from __future__ import annotations

import re
import time
from contextlib import nullcontext
from typing import Iterable, Iterator

from .. import providers
from ..prompts import GENERATE_RAG_SCHEMA, GENERATE_RAG_SYSTEM, GENERATE_RAG_USER
from ..providers.azure_openai import ProviderIncomplete
from ..schemas import (
    BehaviorLabel,
    CoreRecord,
    GenerationMode,
    GeneratorOutput,
    GroundingPassage,
)
from ..trace import TraceWriter
from .base import Step, StepContext

# Default mode if --modes isn't specified
DEFAULT_MODE: GenerationMode = "rag_perturbed"

# Hedging phrases that suggest the model is flagging a contradiction
_CONFLICT_MARKERS = (
    "however", "but the passages", "but the documents", "according to the passages",
    "but according to my", "contradict", "inconsistent", "uncertain",
    "may not be accurate", "differs from", "disagrees with",
)
_REFUSAL_MARKERS = (
    "cannot determine", "insufficient", "not enough information",
    "passages do not", "no information", "unable to answer",
)

_NORM = re.compile(r"[\s\W_]+", re.UNICODE)


def _normalize(s: str) -> str:
    return _NORM.sub(" ", (s or "").lower()).strip()


def _format_passages(passages: list[GroundingPassage]) -> str:
    return "\n\n".join(f"[{p.passage_id}] {p.text}" for p in passages)


def _select_grounding(record: CoreRecord, mode: GenerationMode) -> list[GroundingPassage] | None:
    if mode == "rag_perturbed":
        return record.all_grounding_perturbed or None
    if mode == "rag_original":
        return record.all_grounding_original or None
    if mode == "closed_book":
        return []  # no grounding, but valid mode
    return None


def _resolve_generators(opt: object | None) -> list[str]:
    if isinstance(opt, str) and opt.strip():
        return [t.strip() for t in opt.split(",") if t.strip()]
    if isinstance(opt, list) and opt:
        return [str(t) for t in opt]
    return []


def _behavior_label(
    answer_text: str,
    original_value: str | None,
    perturbed_value: str | None,
    is_refusal: bool,
) -> tuple[BehaviorLabel, bool, bool]:
    """Return (label, entails_original, entails_perturbed) using deterministic normalization."""
    if is_refusal:
        return "refusal_or_insufficient", False, False

    ans_n = _normalize(answer_text)
    ov_n = _normalize(original_value) if original_value else ""
    pv_n = _normalize(perturbed_value) if perturbed_value else ""

    has_orig = bool(ov_n) and ov_n in ans_n
    has_pert = bool(pv_n) and pv_n in ans_n

    ans_lower = (answer_text or "").lower()
    conflict_flag = any(m in ans_lower for m in _CONFLICT_MARKERS)
    refusal_flag = any(m in ans_lower for m in _REFUSAL_MARKERS)

    if has_orig and has_pert:
        return "both_claims", True, True
    if has_pert and not has_orig:
        return "context_follow", False, True
    if has_orig and not has_pert:
        # if it also flags conflict, that's still memory_override (the model
        # used the original despite the perturbed context)
        return "memory_override", True, False
    if conflict_flag and not has_orig and not has_pert:
        return "conflict_awareness", False, False
    if refusal_flag:
        return "refusal_or_insufficient", False, False
    return "unrelated_or_failed", False, False


class GenerateStep(Step):
    name = "generate"
    requires_llm = False  # we manage providers ourselves

    def run_record(self, record: CoreRecord, ctx: StepContext) -> CoreRecord | None:
        gen_names: list[str] = _resolve_generators(ctx.options.get("generators"))
        modes: list[GenerationMode] = _resolve_generators(ctx.options.get("modes")) or [DEFAULT_MODE]  # type: ignore[assignment]

        # Fallback: if --generators not given but --model is, use it as single generator
        if not gen_names:
            single = ctx.options.get("_runner_model")
            if isinstance(single, str) and single:
                gen_names = [single]
        if not gen_names:
            record.pipeline_state["generate"] = "failed:no_generators_specified"
            return record

        any_call_succeeded = False
        any_call_failed = False

        for mode in modes:
            grounding = _select_grounding(record, mode)
            if grounding is None and mode in ("rag_perturbed", "rag_original"):
                record.pipeline_state["generate"] = f"skipped:no_grounding_for_{mode}"
                return record

            for gen_name in gen_names:
                try:
                    provider = providers.get(gen_name)
                except Exception as exc:  # noqa: BLE001
                    record.pipeline_state["generate"] = f"failed:provider_load:{gen_name}:{exc}"
                    return record

                user = GENERATE_RAG_USER.format(
                    question=record.question,
                    passages=_format_passages(grounding or []) if grounding else "(no passages — answer from your own knowledge)",
                )

                trace_cm = (
                    ctx.trace.call(
                        core_id=record.core_id,
                        provider=provider.name,
                        model=provider.model,
                        system_prompt=GENERATE_RAG_SYSTEM,
                        user_prompt=user,
                        metadata={
                            "generator_model": provider.model,
                            "generator_provider": provider.name,
                            "mode": mode,
                        },
                    )
                    if ctx.trace
                    else nullcontext({})
                )

                try:
                    with trace_cm as slot:
                        resp = provider.complete_json(
                            system=GENERATE_RAG_SYSTEM,
                            user=user,
                            schema_hint=GENERATE_RAG_SCHEMA,
                            max_tokens=4096,
                        )
                        slot["raw_response"] = resp.text
                        slot["parsed_output"] = resp.parsed_json
                        slot["input_tokens"] = resp.input_tokens
                        slot["output_tokens"] = resp.output_tokens
                        parsed = resp.parsed_json
                except ProviderIncomplete as exc:
                    any_call_failed = True
                    record.generator_outputs.append(GeneratorOutput(
                        generator_provider=provider.name,
                        generator_model=provider.model,
                        mode=mode,
                        answer_text="",
                        is_refusal=False,
                        behavior_label="unrelated_or_failed",
                        notes=f"llm_{exc.reason}: {str(exc)[:240]}",
                        run_id=ctx.run_id,
                        completed_at=int(time.time()),
                    ))
                    continue

                if not parsed:
                    any_call_failed = True
                    record.generator_outputs.append(GeneratorOutput(
                        generator_provider=provider.name,
                        generator_model=provider.model,
                        mode=mode,
                        answer_text="",
                        is_refusal=False,
                        behavior_label="unrelated_or_failed",
                        notes="no_json",
                        run_id=ctx.run_id,
                        completed_at=int(time.time()),
                    ))
                    continue

                answer_text = str(parsed.get("answer") or "")
                is_refusal = bool(parsed.get("is_refusal"))
                raw_cites = parsed.get("cited_passage_ids") or []
                cites = [int(c) for c in raw_cites if isinstance(c, (int, str)) and str(c).lstrip("-").isdigit()]
                notes = parsed.get("notes")
                if notes is not None:
                    notes = str(notes)[:500]

                label, e_orig, e_pert = _behavior_label(
                    answer_text=answer_text,
                    original_value=record.original_value,
                    perturbed_value=record.perturbed_value,
                    is_refusal=is_refusal,
                )

                record.generator_outputs.append(GeneratorOutput(
                    generator_provider=provider.name,
                    generator_model=provider.model,
                    mode=mode,
                    answer_text=answer_text,
                    cited_passage_ids=cites,
                    is_refusal=is_refusal,
                    entails_original_claim=e_orig,
                    entails_perturbed_claim=e_pert,
                    behavior_label=label,
                    notes=notes,
                    run_id=ctx.run_id,
                    completed_at=int(time.time()),
                ))
                any_call_succeeded = True

        if any_call_succeeded and not any_call_failed:
            record.pipeline_state["generate"] = "ok"
        elif any_call_succeeded:
            record.pipeline_state["generate"] = "ok_partial"
        else:
            record.pipeline_state["generate"] = "failed:all_generators_failed"
        return record
