"""Prompt templates for LLM-driven steps."""
from __future__ import annotations

# ---------- Perturbation (single combined call) ----------

PERTURB_SYSTEM = """\
You are constructing a controlled factual perturbation for a RAG evaluation benchmark.

You will receive:
  - a question
  - a human-written answer that cites grounding passages
  - a set of grounding passages (answer-containing and related-info)

Your job, in ONE pass:

  1. Pick ONE atomic value that is present in the answer AND appears (verbatim or
     paraphrased) in the grounding. The chosen value MUST be answer-causal.

     ANSWER-CAUSALITY TEST (apply before committing to a target):
       Ask yourself the question literally. If a reader were given only the rewritten
       grounding and asked "{question}", would the answer they produce be *materially
       different* with your perturbed value than with the original? If the answer would
       stay essentially the same (e.g. swapping a peripheral named tool, a minor dollar
       figure, an incidental rank when the question is about strategy/impact), then the
       value is NOT answer-causal — pick a different target.

     Prefer values that the question is *literally asking about* (the year for a "when"
     question, the rank for a "what rank" question, the cause for a "what causes"
     question, the entity for a "who founded" question). Avoid peripheral spans.

  2. Choose ONE perturbation type from the closed menu. The perturbed value must be:
     - Plausible (no absurd dates, no nonexistent entities).
     - Type-preserving (date → date, person → person, number → similar magnitude).
     - DEDUCIBLE: a reader who only saw the rewritten passages would arrive at the
       perturbed value without confusion. The rewrite must point unambiguously to the
       new value.

  3. For EVERY passage you receive, return one entry in `doc_modifications`. If the
     passage mentions the chosen value (explicit, paraphrased, or entailed), rewrite
     it consistently so the perturbed value takes its place AND the original value
     disappears entirely from that passage. If the passage does not mention the value,
     include it with `was_modified: false` and a one-line `skip_reason`.

  4. Apply the SAME swap everywhere the original value appears. After your rewrite,
     the original value must not appear in any modified passage. Leave unrelated
     content of each passage intact — only edit the spans tied to the chosen value.

     CONTEXTUAL ANCHORS: also rewrite contextual references that uniquely identify the
     original value: organization names, foundation names, signature programs,
     trademark phrases that would tip the reader off (e.g. if you change "Parkinson's
     disease" → "multiple sclerosis", also rewrite "Michael J. Fox Foundation for
     Parkinson's Research" to a plausible MS-equivalent, or remove the sentence if no
     clean substitute exists). The rewritten passage must read as if the perturbed
     value were the original fact, with no surviving giveaways.

  5. Do not invent new facts beyond the swap itself. Do not edit dates, numbers,
     entities, or relations that are unrelated to the chosen claim.

Return ONLY a single JSON object matching the schema. No prose, no code fences.
"""

PERTURB_SCHEMA = """\
{
  "perturbation_type": "one of: entity_substitution | temporal_shift | numerical_shift | relation_inversion | location_change | affiliation_change | ranking_flip | causal_change | negation_modality | multihop_bridge",
  "perturbation_subtype": "string or null  -- e.g. year_shift, country_swap, percent_change",
  "original_value": "string  -- the exact span you targeted (date, number, entity name)",
  "perturbed_value": "string  -- the replacement",
  "atomic_claim_original": "string  -- one-sentence statement of the original claim",
  "atomic_claim_perturbed": "string  -- one-sentence statement of the perturbed claim",
  "plausibility": "high | medium | low",
  "deducibility_note": "string  -- 1-2 sentences: how the rewritten passages make the new value deducible without revealing the original",
  "doc_modifications": [
    {
      "passage_id": int,
      "was_modified": bool,
      "modified_text": "string or null  -- full rewritten passage text if was_modified, else null",
      "original_span": "string or null  -- the exact text replaced (if was_modified)",
      "perturbed_span": "string or null  -- the replacement text (if was_modified)",
      "mention_kind": "one of: explicit | paraphrased | entailed   (if was_modified, else null)",
      "skip_reason": "string or null  -- one short clause; required when was_modified is false"
    }
  ]
}
"""

PERTURB_USER = """\
QUESTION:
{question}

HUMAN ANSWER:
{answer}

ALLOWED PERTURBATION TYPES (pick one that best fits your chosen claim):
{allowed_types}

GROUNDING PASSAGES (id : label : text):
{passages}

Constraints recap:
- Pick ONE answer-causal atomic value present in both the answer and the grounding.
- Apply the perturbation consistently across EVERY passage that mentions it.
- After your rewrite the original value must not appear in any modified passage.
- Return one `doc_modifications` entry per passage above, even the unmodified ones.
"""

# ---------- Validation ----------

VALIDATE_SYSTEM = """\
You audit a perturbation produced for a RAG benchmark. Grade five booleans + a plausibility rating.

Definitions:
- type_valid: rewritten passages preserve grammar and entity/value type.
- answer_causal: a faithful answer to the question would change if the perturbed claim were true.
- global_context_consistent: every rewritten passage now supports the perturbed claim;
  none still support the original.
- no_original_answer_leakage: the original value does not appear anywhere in the
  PERTURBED PASSAGES section (the original passages naturally still contain it — that
  is expected and is NOT leakage). Also check for surviving contextual anchors that
  uniquely identify the original value (organization names, signature programs, etc.)
  in the PERTURBED PASSAGES; treat those as leakage too.
- original_contradicts_perturbed: the original passages clearly support the original claim
  and contradict the perturbed claim.

Return JSON only.
"""

VALIDATE_SCHEMA = """\
{
  "type_valid": bool,
  "answer_causal": bool,
  "global_context_consistent": bool,
  "no_original_answer_leakage": bool,
  "original_contradicts_perturbed": bool,
  "plausibility": "high | medium | low",
  "rejection_reasons": ["string", ...]
}
"""

VALIDATE_USER = """\
QUESTION:
{question}

ATOMIC CLAIM (original):
{atomic_claim_original}

ATOMIC CLAIM (perturbed):
{atomic_claim_perturbed}

ORIGINAL VALUE: {original_value}
PERTURBED VALUE: {perturbed_value}

ORIGINAL PASSAGES (id : text):
{original_passages}

PERTURBED PASSAGES (id : text):
{perturbed_passages}

Audit per the schema. List specific rejection_reasons whenever any label is false.
"""
