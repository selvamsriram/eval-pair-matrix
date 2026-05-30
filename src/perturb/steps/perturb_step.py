"""Combined claim-pick + rewrite step (replaces the old claim+mentions+perturb chain).

Inputs (from filter step):
  - question, answer, all_grounding_original, answer_containing_passage_ids

Pipeline within this step:
  1. Send Q + A + (ANSWER-THE-QUESTION ∪ RELATED-INFORMATION) passages to the LLM.
  2. Parse the response: single perturbation spec + one DocModification per sent passage.
  3. Build all_grounding_perturbed by swapping modified_text for modified docs.
  4. Deterministic backstop: for any passage we did NOT send to the LLM, if the
     original_value appears, regex-swap it locally. This catches leakage in
     UNKNOWN / IRRELEVANT passages without burning more tokens.
  5. Final leakage check: if the original_value still appears anywhere in
     all_grounding_perturbed, mark failed:leakage.
"""
from __future__ import annotations

import re
from contextlib import nullcontext

from ..prompts import PERTURB_SCHEMA, PERTURB_SYSTEM, PERTURB_USER
from ..providers.azure_openai import ProviderIncomplete
from ..schemas import (
    PERTURBATION_TYPES,
    CoreRecord,
    DocModification,
    GroundingPassage,
)
from .base import Step, StepContext

# Labels we will send to the perturber. ANSWER-THE-QUESTION carries the target
# claim; RELATED-INFORMATION may mention it incidentally and so must also be
# rewritten consistently to avoid leakage.
LLM_INPUT_LABELS = {"ANSWER-THE-QUESTION", "RELATED-INFORMATION"}

_LEAKAGE_NORM = re.compile(r"[\s\W_]+", re.UNICODE)


def _normalize_for_leakage(s: str) -> str:
    """Collapse whitespace, punctuation, hyphens, case so 'load balancing' matches
    'Load-balancing' and "Parkinson's disease" matches 'parkinsons disease'."""
    return _LEAKAGE_NORM.sub(" ", (s or "").lower()).strip()


def _label_of(p: GroundingPassage) -> str:
    return (p.evidence_correct or "UNLABELED").upper()


def _passages_for_llm(record: CoreRecord) -> list[GroundingPassage]:
    return [p for p in record.all_grounding_original if _label_of(p) in LLM_INPUT_LABELS]


def _format_passages(passages: list[GroundingPassage]) -> str:
    parts = []
    for p in passages:
        label = _label_of(p)
        parts.append(f"[{p.passage_id}] [{label}] {p.text}")
    return "\n\n".join(parts)


def _resolve_allowed_types(opt: object | None) -> list[str]:
    if isinstance(opt, str) and opt.strip():
        return [t.strip() for t in opt.split(",") if t.strip()]
    if isinstance(opt, list) and opt:
        return [str(t) for t in opt]
    return list(PERTURBATION_TYPES)


class PerturbStep(Step):
    name = "perturb"
    requires_llm = True

    def run_record(self, record: CoreRecord, ctx: StepContext) -> CoreRecord | None:
        if ctx.provider is None:
            raise RuntimeError("perturb step requires --model")

        sent = _passages_for_llm(record)
        if not sent:
            record.pipeline_state["perturb"] = "skipped:no_answer_or_related_passages"
            return record

        allowed_types = _resolve_allowed_types(ctx.options.get("types"))
        user = PERTURB_USER.format(
            question=record.question,
            answer=record.answer_generate,
            allowed_types="\n".join(f"- {t}" for t in allowed_types),
            passages=_format_passages(sent),
        )

        record.sent_passage_ids = [p.passage_id for p in sent]

        trace_cm = (
            ctx.trace.call(
                core_id=record.core_id,
                provider=ctx.provider.name,
                model=ctx.provider.model,
                system_prompt=PERTURB_SYSTEM,
                user_prompt=user,
            )
            if ctx.trace
            else nullcontext({})
        )

        try:
            with trace_cm as slot:
                resp = ctx.provider.complete_json(
                    system=PERTURB_SYSTEM,
                    user=user,
                    schema_hint=PERTURB_SCHEMA,
                    max_tokens=12_288,
                )
                slot["raw_response"] = resp.text
                slot["parsed_output"] = resp.parsed_json
                slot["input_tokens"] = resp.input_tokens
                slot["output_tokens"] = resp.output_tokens
                parsed = resp.parsed_json
        except ProviderIncomplete as exc:
            record.pipeline_state["perturb"] = f"failed:llm_{exc.reason}"
            return record

        if not parsed:
            record.pipeline_state["perturb"] = "failed:no_json"
            return record

        # ---- Pull top-level perturbation spec ----
        try:
            original_value = str(parsed["original_value"]).strip()
            perturbed_value = str(parsed["perturbed_value"]).strip()
            ptype = str(parsed["perturbation_type"]).strip()
        except (KeyError, TypeError):
            record.pipeline_state["perturb"] = "failed:bad_spec"
            return record

        if not original_value or not perturbed_value:
            record.pipeline_state["perturb"] = "failed:empty_values"
            return record
        if original_value == perturbed_value:
            record.pipeline_state["perturb"] = "failed:identical_values"
            return record
        if ptype not in PERTURBATION_TYPES:
            record.pipeline_state["perturb"] = f"failed:unknown_type:{ptype}"
            return record

        record.original_value = original_value
        record.perturbed_value = perturbed_value
        record.perturbation_type = ptype  # type: ignore[assignment]
        record.perturbation_subtype = parsed.get("perturbation_subtype")
        record.atomic_claim_original = parsed.get("atomic_claim_original")
        record.atomic_claim_perturbed = parsed.get("atomic_claim_perturbed")
        record.plausibility = parsed.get("plausibility")
        record.deducibility_note = parsed.get("deducibility_note")

        # ---- Pull per-doc modifications ----
        raw_mods = parsed.get("doc_modifications") or []
        mods_by_id: dict[int, DocModification] = {}
        for entry in raw_mods:
            try:
                pid = int(entry["passage_id"])
            except (KeyError, TypeError, ValueError):
                continue
            try:
                mod = DocModification(
                    passage_id=pid,
                    was_modified=bool(entry.get("was_modified", False)),
                    modified_text=entry.get("modified_text"),
                    original_span=entry.get("original_span"),
                    perturbed_span=entry.get("perturbed_span"),
                    mention_kind=entry.get("mention_kind"),
                    skip_reason=entry.get("skip_reason"),
                )
            except Exception:  # noqa: BLE001 — bad entry, skip
                continue
            mods_by_id[pid] = mod
        record.doc_modifications = list(mods_by_id.values())

        # ---- Build all_grounding_perturbed ----
        ov_lower = original_value.lower()
        ov_norm = _normalize_for_leakage(original_value)
        sent_ids = set(record.sent_passage_ids)
        modified_ids: list[int] = []
        backstop_ids: list[int] = []
        perturbed_passages: list[GroundingPassage] = []

        for p in record.all_grounding_original:
            mod = mods_by_id.get(p.passage_id)
            if mod and mod.was_modified and mod.modified_text:
                perturbed_passages.append(
                    GroundingPassage(
                        passage_id=p.passage_id,
                        text=mod.modified_text,
                        provider=p.provider,
                        passage_date=p.passage_date,
                        evidence_relevant=p.evidence_relevant,
                        evidence_correct=p.evidence_correct,
                        evidence_cited=p.evidence_cited,
                        was_modified=True,
                    )
                )
                modified_ids.append(p.passage_id)
                continue

            # Not modified by the LLM. If we did NOT send it AND it leaks the
            # original value, apply the deterministic backstop swap.
            if p.passage_id not in sent_ids and ov_norm and ov_norm in _normalize_for_leakage(p.text):
                new_text = re.sub(
                    re.escape(original_value),
                    perturbed_value,
                    p.text,
                    flags=re.IGNORECASE,
                )
                perturbed_passages.append(
                    GroundingPassage(
                        passage_id=p.passage_id,
                        text=new_text,
                        provider=p.provider,
                        passage_date=p.passage_date,
                        evidence_relevant=p.evidence_relevant,
                        evidence_correct=p.evidence_correct,
                        evidence_cited=p.evidence_cited,
                        was_modified=True,
                    )
                )
                modified_ids.append(p.passage_id)
                backstop_ids.append(p.passage_id)
            else:
                perturbed_passages.append(p.model_copy())

        record.all_grounding_perturbed = perturbed_passages
        record.modified_passage_ids = modified_ids
        record.backstop_modified_passage_ids = backstop_ids

        # ---- Final leakage check ----
        leakage = [
            p.passage_id
            for p in perturbed_passages
            if ov_norm and ov_norm in _normalize_for_leakage(p.text)
        ]
        if leakage:
            record.pipeline_state["perturb"] = f"failed:leakage:{leakage}"
            return record

        # ---- Coverage sanity: every sent passage should have a doc_modifications entry ----
        missing = [pid for pid in sent_ids if pid not in mods_by_id]
        if missing:
            record.pipeline_state["perturb"] = f"failed:missing_doc_entries:{missing}"
            return record

        record.pipeline_state["perturb"] = "ok"
        return record
