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


# ---------- Provider families (used by Phase 2 judge-pair derivation) ----------

# Registry-name → family. Add a line per new provider as you wire it.
# Used to derive judge-vs-generator `pair_type`: same_exact_model,
# same_provider_family, or cross_provider_family.
PROVIDER_FAMILY: dict[str, str] = {
    "azure-gpt": "openai_family",
    "grok": "xai_family",
    "gemini": "google_family",
    "kimi": "moonshot_family",
    "anthropic": "anthropic_family",
}


def provider_family(provider_name: str) -> str:
    return PROVIDER_FAMILY.get(provider_name, "unknown_family")


# ---------- Generation (Phase 2) ----------

GenerationMode = Literal["rag_perturbed", "rag_original", "closed_book"]

# Deterministic post-generation classification of how the answer relates to the
# original vs perturbed claim. Computed inline by the generate step.
BehaviorLabel = Literal[
    "context_follow",           # answer uses perturbed value, not original
    "memory_override",          # answer uses original value, not perturbed
    "both_claims",              # answer mentions both
    "conflict_awareness",       # answer flags a contradiction / uncertainty
    "refusal_or_insufficient",  # model declined / said evidence insufficient
    "unrelated_or_failed",      # neither value present and not a refusal
]


PairType = Literal["same_exact_model", "same_provider_family", "cross_provider_family"]


def derive_pair_type(
    judge_provider: str,
    judge_model: str,
    generator_provider: str,
    generator_model: str,
) -> PairType:
    """Classify a (judge, generator) pair for the eval-pair matrix.

    same_exact_model     : judge and generator are the same model instance.
    same_provider_family : different exact models from the same provider family
                           (e.g., gpt-5.4 judging gpt-5.5 — would be openai_family).
    cross_provider_family: different provider families.
    """
    if judge_provider == generator_provider and judge_model == generator_model:
        return "same_exact_model"
    if provider_family(judge_provider) == provider_family(generator_provider):
        return "same_provider_family"
    return "cross_provider_family"


class JudgeVerdict(BaseModel):
    """One judge model's verdict on one GeneratorOutput.

    The judge sees only (question, answer, ORIGINAL grounding). It does NOT see
    the perturbation, the perturbed grounding, or the deterministic labels.
    Gold labels below are derived externally from the generator's LLM-eval
    output and are NEVER shown to the judge — they're carried on the verdict
    purely so downstream analysis can compute precision/recall/F1 per pair_type.
    """
    # Identity
    judge_provider: str           # registry key, e.g. "azure-gpt"
    judge_model: str              # exact id, e.g. "gpt-5.4"

    # Which generator output is being judged
    generator_provider: str
    generator_model: str
    generator_mode: "GenerationMode"
    generator_sample_id: int = 0

    # Auto-derived pair classification
    pair_type: PairType

    # The judge's verdict
    verdict: Literal["correct", "incorrect", "unclear"]
    contains_factual_error: bool
    wrong_claim: str | None = None                  # judge's text for the wrong claim
    supporting_source_passage_id: int | None = None # passage ID the judge points to
    explanation: str | None = None
    confidence: Plausibility | None = None

    # Gold labels (NOT shown to judge; populated from generator's llm_eval)
    gold_has_induced_error: bool                    # True if generator asserted perturbed value
    gold_perturbation_target: str | None = None     # = original_value (what truth is)
    gold_perturbation_replacement: str | None = None # = perturbed_value (what the answer should NOT say)

    # Provenance
    run_id: str
    completed_at: int


class LLMBehaviorEval(BaseModel):
    """An LLM evaluator's classification of one GeneratorOutput.

    Produced by the `label_eval` step; lives ALONGSIDE the deterministic
    `behavior_label` on its parent GeneratorOutput so we can compare code-based
    and LLM-based labels per record.
    """
    evaluator_provider: str       # registry key, e.g. "azure-gpt"
    evaluator_model: str          # exact id, e.g. "gpt-5.4"
    behavior_label: BehaviorLabel
    entails_original_claim: bool
    entails_perturbed_claim: bool
    rationale: str | None = None
    confidence: Plausibility | None = None  # reuses high|medium|low
    run_id: str
    completed_at: int


class GeneratorOutput(BaseModel):
    """One LLM-generated answer for a specific (model, mode) combination.

    Multiple outputs can exist per CoreRecord (one per generator, optionally
    multiple samples for closed-book probes).
    """
    generator_provider: str   # registry key, e.g. "azure-gpt"
    generator_model: str      # exact model id, e.g. "gpt-5.4"
    mode: GenerationMode
    sample_id: int = 0        # 0 unless multi-sample (closed-book uses 0..N-1)
    answer_text: str
    cited_passage_ids: list[int] = Field(default_factory=list)
    is_refusal: bool = False

    # Deterministic post-gen analysis (computed inline by generate step)
    entails_original_claim: bool | None = None
    entails_perturbed_claim: bool | None = None
    behavior_label: BehaviorLabel | None = None
    notes: str | None = None  # any free-form notes the model emitted

    # LLM-driven re-evaluation (populated by label_eval step). Carries the
    # evaluator's own behavior_label / entailments so we can diff against the
    # deterministic ones above per record.
    llm_eval: LLMBehaviorEval | None = None

    # When/where this came from
    run_id: str
    completed_at: int


class StepProvenance(BaseModel):
    """Who/when produced this step's output for a given record.

    Stamped automatically by the runner. Last-writer-wins on re-runs / cross-model
    overlap (e.g. perturb with GPT-5, then re-validate the same records with Kimi
    via --resume) — full history remains in data/traces/<run_id>/<step>.jsonl.
    """
    provider: str           # registry key, e.g. "azure-gpt" | "kimi" | "anthropic"
    model: str              # exact model id, e.g. "gpt-5.4" | "kimi-k2.6"
    run_id: str
    completed_at: int       # epoch seconds


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

    # Per-step model attribution: step_name -> StepProvenance. Auto-stamped by the
    # runner for any step that used an LLM. Filter has no entry (deterministic).
    generators: dict[str, StepProvenance] = Field(default_factory=dict)

    # Step 4 (generate): one GeneratorOutput per (model, mode, sample) combination.
    # Appended across runs — analysis filters by run_id / generator_model / mode.
    generator_outputs: list[GeneratorOutput] = Field(default_factory=list)

    # Step 6 (judge): one JudgeVerdict per (judge_model, generator_output) pair.
    # Same append-only pattern: each judge run extends the list rather than
    # replacing. Filter by (judge_model, generator_model, run_id) for analysis.
    judge_verdicts: list[JudgeVerdict] = Field(default_factory=list)
