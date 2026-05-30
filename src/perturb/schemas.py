"""Single growing CoreRecord; fields populate as the pipeline advances.

Pipeline: filter → perturb → validate. Each step adds fields; downstream steps
require upstream fields.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# ---------- Sub-models ----------

MentionKind = Literal["explicit", "paraphrased", "entailed"]
Plausibility = Literal["high", "medium", "low"]

# Closed menu of perturbation categories. Model picks one per example.
PerturbationType = Literal[
    "entity_substitution",
    "temporal_shift",
    "numerical_shift",
    "relation_inversion",
    "location_change",
    "affiliation_change",
    "ranking_flip",
    "causal_change",
    "negation_modality",
    "multihop_bridge",
]

PERTURBATION_TYPES: list[str] = [
    "entity_substitution",
    "temporal_shift",
    "numerical_shift",
    "relation_inversion",
    "location_change",
    "affiliation_change",
    "ranking_flip",
    "causal_change",
    "negation_modality",
    "multihop_bridge",
]


class GroundingPassage(BaseModel):
    model_config = ConfigDict(extra="allow")
    passage_id: int
    text: str
    provider: str | None = None
    passage_date: str | None = None
    evidence_relevant: str | None = None
    evidence_correct: str | None = None
    evidence_cited: str | None = None
    was_modified: bool = False


class DocModification(BaseModel):
    """One entry per passage we sent to the perturber.

    `was_modified=False` records also appear so we can audit coverage decisions.
    No char offsets: spans are stored as text only.
    """
    passage_id: int
    was_modified: bool
    modified_text: str | None = None
    original_span: str | None = None
    perturbed_span: str | None = None
    mention_kind: MentionKind | None = None
    skip_reason: str | None = None


class Validation(BaseModel):
    type_valid: bool | None = None
    answer_causal: bool | None = None
    global_context_consistent: bool | None = None
    no_original_answer_leakage: bool | None = None
    original_contradicts_perturbed: bool | None = None
    plausibility: Plausibility | None = None
    human_audited: bool = False
    rejection_reasons: list[str] = Field(default_factory=list)

    @property
    def passes(self) -> bool:
        gates = (
            self.type_valid,
            self.answer_causal,
            self.global_context_consistent,
            self.no_original_answer_leakage,
            self.original_contradicts_perturbed,
        )
        return all(g is True for g in gates)


# ---------- Top-level record ----------


class CoreRecord(BaseModel):
    """The single growing record carried through the pipeline.

    Fields are populated in step order; downstream steps require upstream fields.
    """

    model_config = ConfigDict(extra="ignore")

    # Step 1 (filter): identity + raw GaRAGe carryover
    core_id: str
    garage_sample_id: str
    question: str
    question_date: str | None = None
    question_category: str | None = None
    question_complexity: str | None = None
    question_popularity: str | None = None
    question_type: str | None = None
    answer_generate: str = ""

    all_grounding_original: list[GroundingPassage] = Field(default_factory=list)
    answer_containing_passage_ids: list[int] = Field(default_factory=list)

    # Step 2 (perturb): combined claim selection + rewrite
    atomic_claim_original: str | None = None
    atomic_claim_perturbed: str | None = None
    original_value: str | None = None
    perturbed_value: str | None = None
    perturbation_type: PerturbationType | None = None
    perturbation_subtype: str | None = None
    plausibility: Plausibility | None = None
    deducibility_note: str | None = None

    # Which passages we sent to the model (audit trail)
    sent_passage_ids: list[int] = Field(default_factory=list)
    # The model's per-doc decisions, one entry per sent passage
    doc_modifications: list[DocModification] = Field(default_factory=list)
    # Passages touched by the deterministic leakage backstop (not seen by LLM)
    backstop_modified_passage_ids: list[int] = Field(default_factory=list)
    # Union of LLM-modified + backstop-modified
    modified_passage_ids: list[int] = Field(default_factory=list)
    # Full perturbed grounding (same passage_ids as original, with `was_modified` set)
    all_grounding_perturbed: list[GroundingPassage] = Field(default_factory=list)

    # Step 3 (validation)
    validation: Validation = Field(default_factory=Validation)

    # Step provenance: name -> "ok" | "skipped:<reason>" | "failed:<reason>"
    pipeline_state: dict[str, str] = Field(default_factory=dict)
