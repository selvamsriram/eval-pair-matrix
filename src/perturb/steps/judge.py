"""Step 6: judge — one or more LLM judges evaluate every GeneratorOutput.

Each judge sees only (question, generator's answer, ORIGINAL grounding). It
does NOT see the perturbation, the perturbed grounding, the deterministic
labels, or the LLM-eval labels — the judge is blind to ground truth and
must decide purely from authoritative source passages.

Gold labels (`gold_has_induced_error` etc.) are derived from the generator's
LLM-eval and attached to each JudgeVerdict so analysis can compute
precision / recall / F1 per pair_type without joining anything.

CLI:
  perturb judge --run <id> --judges azure-gpt,grok,gemini

Each judge gets one LLM call per (record × generator_output). With 300
records, 3 generators, 3 judges = 2,700 calls per full matrix.
"""
from __future__ import annotations

import time
from contextlib import nullcontext

from .. import providers
from ..prompts import JUDGE_SCHEMA, JUDGE_SYSTEM, JUDGE_USER
from ..providers.azure_openai import ProviderIncomplete
from ..schemas import (
    CoreRecord,
    GeneratorOutput,
    GroundingPassage,
    JudgeVerdict,
    derive_pair_type,
)
from .base import Step, StepContext


def _resolve_list(opt: object | None) -> list[str]:
    if isinstance(opt, str) and opt.strip():
        return [t.strip() for t in opt.split(",") if t.strip()]
    if isinstance(opt, list) and opt:
        return [str(t) for t in opt]
    return []


def _format_passages(passages: list[GroundingPassage]) -> str:
    return "\n\n".join(f"[{p.passage_id}] {p.text}" for p in passages)


def _derive_gold(record: CoreRecord, g: GeneratorOutput) -> tuple[bool, str | None, str | None]:
    """Gold ground truth for one generator output.

    has_induced_error = True iff the generator asserted the PERTURBED value as
    fact (i.e., the answer contains a claim contradicted by the ORIGINAL
    source). Uses LLM eval labels (preferred) and falls back to deterministic.
    """
    target = record.original_value
    replacement = record.perturbed_value
    ev = g.llm_eval
    if ev is not None:
        # Most precise gold: LLM said the answer entails the perturbed claim.
        if ev.entails_perturbed_claim and not ev.entails_original_claim:
            return True, target, replacement
        if ev.behavior_label == "context_follow":
            return True, target, replacement
        if ev.behavior_label == "both_claims" and ev.entails_perturbed_claim:
            return True, target, replacement
        return False, target, replacement
    # Fallback to deterministic
    if g.behavior_label == "context_follow":
        return True, target, replacement
    return False, target, replacement


def _judge_one(
    record: CoreRecord,
    g: GeneratorOutput,
    judge_name: str,
    judge_provider: object,
    ctx: StepContext,
) -> JudgeVerdict | None:
    """One judge model evaluates one generator output."""
    user = JUDGE_USER.format(
        question=record.question,
        answer=g.answer_text or "(empty)",
        passages=_format_passages(record.all_grounding_original or []),
    )

    pair_type = derive_pair_type(
        judge_provider=judge_provider.name,
        judge_model=judge_provider.model,
        generator_provider=g.generator_provider,
        generator_model=g.generator_model,
    )

    gold_err, gold_target, gold_replacement = _derive_gold(record, g)

    trace_cm = (
        ctx.trace.call(
            core_id=record.core_id,
            provider=judge_provider.name,
            model=judge_provider.model,
            system_prompt=JUDGE_SYSTEM,
            user_prompt=user,
            metadata={
                "judge_model": judge_provider.model,
                "judge_provider": judge_provider.name,
                "generator_model": g.generator_model,
                "generator_provider": g.generator_provider,
                "generator_mode": g.mode,
                "pair_type": pair_type,
                "gold_has_induced_error": gold_err,
            },
        )
        if ctx.trace
        else nullcontext({})
    )

    try:
        with trace_cm as slot:
            resp = judge_provider.complete_json(
                system=JUDGE_SYSTEM,
                user=user,
                schema_hint=JUDGE_SCHEMA,
                max_tokens=1024,
            )
            slot["raw_response"] = resp.text
            slot["parsed_output"] = resp.parsed_json
            slot["input_tokens"] = resp.input_tokens
            slot["output_tokens"] = resp.output_tokens
            parsed = resp.parsed_json
    except ProviderIncomplete:
        return None

    if not parsed:
        return None

    verdict = parsed.get("verdict")
    if verdict not in ("correct", "incorrect", "unclear"):
        return None

    sid = parsed.get("supporting_source_passage_id")
    try:
        sid_int = int(sid) if sid is not None else None
    except (TypeError, ValueError):
        sid_int = None

    confidence = parsed.get("confidence")
    confidence = confidence if confidence in ("high", "medium", "low") else None

    return JudgeVerdict(
        judge_provider=judge_provider.name,
        judge_model=judge_provider.model,
        generator_provider=g.generator_provider,
        generator_model=g.generator_model,
        generator_mode=g.mode,
        generator_sample_id=g.sample_id,
        pair_type=pair_type,
        verdict=verdict,  # type: ignore[arg-type]
        contains_factual_error=bool(parsed.get("contains_factual_error")),
        wrong_claim=(str(parsed.get("wrong_claim"))[:600] if parsed.get("wrong_claim") else None),
        supporting_source_passage_id=sid_int,
        explanation=(str(parsed.get("explanation"))[:600] if parsed.get("explanation") else None),
        confidence=confidence,  # type: ignore[arg-type]
        gold_has_induced_error=gold_err,
        gold_perturbation_target=gold_target,
        gold_perturbation_replacement=gold_replacement,
        run_id=ctx.run_id,
        completed_at=int(time.time()),
    )


class JudgeStep(Step):
    name = "judge"
    requires_llm = False  # manages its own provider list

    def run_record(self, record: CoreRecord, ctx: StepContext) -> CoreRecord | None:
        judge_names = _resolve_list(ctx.options.get("judges"))
        # Fallback: --model becomes single judge
        if not judge_names:
            single = ctx.options.get("_runner_model")
            if isinstance(single, str) and single:
                judge_names = [single]
        if not judge_names:
            record.pipeline_state["judge"] = "failed:no_judges_specified"
            return record

        if not record.generator_outputs:
            record.pipeline_state["judge"] = "skipped:no_generator_outputs"
            return record

        # Cache provider instances per judge_name to avoid re-construction per record
        cache: dict[str, object] = {}
        for jn in judge_names:
            try:
                cache[jn] = providers.get(jn)
            except Exception as exc:  # noqa: BLE001
                record.pipeline_state["judge"] = f"failed:judge_load:{jn}:{exc}"
                return record

        any_ok = any_failed = 0
        for g in record.generator_outputs:
            for jn in judge_names:
                judge_provider = cache[jn]
                # Skip outputs with no answer (failed generations) — judge can't evaluate
                if not (g.answer_text or "").strip():
                    continue
                ev = _judge_one(record, g, jn, judge_provider, ctx)
                if ev is None:
                    any_failed += 1
                    continue
                record.judge_verdicts.append(ev)
                any_ok += 1

        if any_ok and not any_failed:
            record.pipeline_state["judge"] = "ok"
        elif any_ok:
            record.pipeline_state["judge"] = "ok_partial"
        else:
            record.pipeline_state["judge"] = "failed:all_judges_failed"
        return record
