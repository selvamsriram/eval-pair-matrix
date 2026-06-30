"""Behavior-sliced paired sensitivity table for the revised paper.

The main paired estimand compares, for the same candidate answer, the matching
judge against the mean of the two non-matching judges. This script recomputes
that estimand on validated records after filtering generator answers by the
LLM behavior label.

Outputs:
  tables/behavior_paired_sensitivity.json
  tables/behavior_paired_sensitivity.tex
"""
from __future__ import annotations

import json
import os
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = Path(__file__).resolve().parent / "tables"

PROVIDERS = ["GPT", "Grok", "Gemini"]
GATES = [
    "type_valid",
    "answer_causal",
    "global_context_consistent",
    "no_original_answer_leakage",
    "original_contradicts_perturbed",
]

CORE_PATH = "data/exp/3provider_300.jsonl"
LABEL_RUNS = {
    "GPT": "data/runs/20260531-005101-gen-gpt55-300/05_label_eval.jsonl",
    "Grok": "data/runs/20260531-005112-gen-grok-300/05_label_eval.jsonl",
    "Gemini": "data/runs/20260531-005123-gen-gemini-300/05_label_eval.jsonl",
}
JUDGE_RUNS = {
    ("GPT", "GPT"): "data/runs/20260531-175601-judge-gpt-on-gpt/06_judge.jsonl",
    ("Grok", "GPT"): "data/runs/20260531-175608-judge-grok-on-gpt/06_judge.jsonl",
    ("Gemini", "GPT"): "data/runs/20260531-175617-judge-gemini-on-gpt/06_judge.jsonl",
    ("GPT", "Grok"): "data/runs/20260531-212107-judge-gpt-on-grok/06_judge.jsonl",
    ("Grok", "Grok"): "data/runs/20260531-212359-judge-grok-on-grok/06_judge.jsonl",
    ("Gemini", "Grok"): "data/runs/20260531-212120-judge-gemini-on-grok/06_judge.jsonl",
    ("GPT", "Gemini"): "data/runs/20260531-230842-judge-gpt-on-gemini/06_judge.jsonl",
    ("Grok", "Gemini"): "data/runs/20260531-230848-judge-grok-on-gemini/06_judge.jsonl",
    ("Gemini", "Gemini"): "data/runs/20260531-230857-judge-gemini-on-gemini/06_judge.jsonl",
}

N_BOOT = int(os.environ.get("PAIRED_BOOTSTRAP", "10000"))
SEED = int(os.environ.get("PAIRED_SEED", "20260627"))
MIN_NEG_FOR_TABLE = 10


def rows(path: str) -> list[dict]:
    return [
        json.loads(line)
        for line in (ROOT / path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def passes(record: dict) -> bool:
    validation = record.get("validation") or {}
    return all(validation.get(gate) is True for gate in GATES)


def r1(value: float | None) -> float | None:
    return None if value is None else round(float(value), 1)


def fmt_stat(stat: dict, allow: bool = True) -> str:
    if not allow or stat["delta"] is None:
        return "--"
    return f"{stat['delta']:+.1f} [{stat['ci_low']:+.1f},{stat['ci_high']:+.1f}]"


core = rows(CORE_PATH)
validated_ids = {record["core_id"] for record in core if passes(record)}
core_ids = sorted(record["core_id"] for record in core)
core_index = {core_id: idx for idx, core_id in enumerate(core_ids)}
n_cores = len(core_ids)
validated_core_idx = sorted(core_index[core_id] for core_id in validated_ids)

behavior_label: dict[tuple[str, str, str], str | None] = {}
for generator, path in LABEL_RUNS.items():
    for record in rows(path):
        for output in record.get("generator_outputs") or []:
            behavior_label[(record["core_id"], generator, output.get("sample_id"))] = (
                output.get("llm_eval") or {}
            ).get("behavior_label")

preds_by_answer: dict[tuple[str, str, str], dict[str, int]] = defaultdict(dict)
gold_by_answer: dict[tuple[str, str, str], bool] = {}
valid_by_answer: dict[tuple[str, str, str], bool] = {}
gen_by_answer: dict[tuple[str, str, str], str] = {}
core_by_answer: dict[tuple[str, str, str], str] = {}
behavior_by_answer: dict[tuple[str, str, str], str | None] = {}

for (judge, generator), path in JUDGE_RUNS.items():
    for record in rows(path):
        core_id = record["core_id"]
        for verdict in record.get("judge_verdicts") or []:
            sample_id = verdict.get("generator_sample_id")
            key = (core_id, generator, sample_id)
            preds_by_answer[key][judge] = int(bool(verdict.get("contains_factual_error")))
            gold_by_answer[key] = bool(verdict.get("gold_has_induced_error"))
            valid_by_answer[key] = core_id in validated_ids
            gen_by_answer[key] = generator
            core_by_answer[key] = core_id
            behavior_by_answer[key] = behavior_label.get(key)

a_core = []
a_gen = []
a_same = []
a_cross = []
a_delta = []
a_gold = []
a_valid = []
a_behavior = []

for key, preds in preds_by_answer.items():
    generator = gen_by_answer[key]
    if generator not in preds:
        continue
    cross = [pred for judge, pred in preds.items() if judge != generator]
    if not cross:
        continue
    same = preds[generator]
    cross_mean = float(np.mean(cross))
    a_core.append(core_index[core_by_answer[key]])
    a_gen.append(generator)
    a_same.append(float(same))
    a_cross.append(cross_mean)
    a_delta.append(float(same) - cross_mean)
    a_gold.append(bool(gold_by_answer[key]))
    a_valid.append(bool(valid_by_answer[key]))
    a_behavior.append(behavior_by_answer[key])

a_core = np.asarray(a_core, dtype=np.int64)
a_gen = np.asarray(a_gen)
a_same = np.asarray(a_same, dtype=float)
a_cross = np.asarray(a_cross, dtype=float)
a_delta = np.asarray(a_delta, dtype=float)
a_gold = np.asarray(a_gold, dtype=bool)
a_valid = np.asarray(a_valid, dtype=bool)
a_behavior = np.asarray(a_behavior, dtype=object)


class Resampler:
    def __init__(self, pop_core_idx: list[int], seed: int):
        self.pop = np.asarray(sorted(pop_core_idx), dtype=np.int64)
        self.npop = len(self.pop)
        rng = np.random.default_rng(seed)
        self.weights = rng.multinomial(
            self.npop, np.full(self.npop, 1.0 / self.npop), size=N_BOOT
        ).astype(np.float64)

    def stat(self, mask: np.ndarray) -> dict:
        if int(mask.sum()) == 0:
            return {
                "n": 0,
                "same_mean": None,
                "cross_mean": None,
                "delta": None,
                "ci_low": None,
                "ci_high": None,
            }
        core_ids_for_answers = a_core[mask]
        deltas = a_delta[mask]
        sum_delta_core = np.bincount(
            core_ids_for_answers, weights=deltas, minlength=n_cores
        )[self.pop]
        cnt_core = np.bincount(core_ids_for_answers, minlength=n_cores).astype(float)[
            self.pop
        ]
        point = float(sum_delta_core.sum() / cnt_core.sum())
        numer = self.weights @ sum_delta_core
        denom = self.weights @ cnt_core
        reps = numer[denom > 0] / denom[denom > 0]
        lo, hi = np.percentile(reps, [2.5, 97.5])
        return {
            "n": int(mask.sum()),
            "n_clusters": self.npop,
            "same_mean": r1(100 * a_same[mask].mean()),
            "cross_mean": r1(100 * a_cross[mask].mean()),
            "delta": r1(100 * point),
            "ci_low": r1(100 * lo),
            "ci_high": r1(100 * hi),
        }


resampler = Resampler(validated_core_idx, SEED)


def block(mask: np.ndarray) -> dict:
    mask = mask & a_valid
    return {
        "n_answers": int(mask.sum()),
        "n_adopted": int((mask & a_gold).sum()),
        "n_avoided": int((mask & ~a_gold).sum()),
        "recall_delta": resampler.stat(mask & a_gold),
        "avoided_claim_flag_delta": resampler.stat(mask & ~a_gold),
        "all_answer_flag_delta": resampler.stat(mask),
    }


slices = {
    "All validated": np.ones(len(a_valid), dtype=bool),
    "Context-follow only": a_behavior == "context_follow",
    "Context-follow + both-claims": (a_behavior == "context_follow")
    | (a_behavior == "both_claims"),
    "Excluding refusal/conflict/unrelated": (
        (a_behavior == "context_follow")
        | (a_behavior == "both_claims")
        | (a_behavior == "memory_override")
    ),
}

report = {
    "meta": {
        "set": "validated records only",
        "estimand": "same-model matching judge minus mean of non-matching judges on the same answer",
        "bootstrap": {
            "method": "cluster bootstrap by validated core_id",
            "clusters": len(validated_core_idx),
            "replicates": N_BOOT,
            "seed": SEED,
        },
        "avoided_claim_display_rule": f"shown only when slice has at least {MIN_NEG_FOR_TABLE} avoided-claim answers",
    },
    "slices": {name: block(mask) for name, mask in slices.items()},
}

OUT_DIR.mkdir(exist_ok=True)
(OUT_DIR / "behavior_paired_sensitivity.json").write_text(
    json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
)


def make_tex() -> str:
    display = {
        "All validated": "All validated",
        "Context-follow only": "Context-follow only",
        "Context-follow + both-claims": "Context + both-claims",
        "Excluding refusal/conflict/unrelated": "No refusal, conflict, or unrelated",
    }
    lines = [
        "% Auto-generated by behavior_paired_sensitivity.py -- do not edit by hand.",
        r"\begin{table}[H]",
        r"\centering",
        r"\scriptsize",
        r"\setlength{\tabcolsep}{2.5pt}",
        r"\begin{tabularx}{\linewidth}{@{}Y r c c c@{}}",
        r"\toprule",
        r"Slice & Answers & Recall $\Delta$ & \makecell{Avoided-claim\\flag $\Delta$} & \makecell{All-answer\\flag $\Delta$} \\",
        r"\midrule",
    ]
    for name, data in report["slices"].items():
        neg_ok = data["n_avoided"] >= MIN_NEG_FOR_TABLE
        lines.append(
            f"{display.get(name, name)} & {data['n_answers']} & "
            f"{fmt_stat(data['recall_delta'])} & "
            f"{fmt_stat(data['avoided_claim_flag_delta'], allow=neg_ok)} & "
            f"{fmt_stat(data['all_answer_flag_delta'])} \\\\"
        )
    lines.extend(
        [
            r"\bottomrule",
            r"\end{tabularx}",
            r"\caption{Behavior-sliced paired sensitivities on validated records. Deltas are matching judge minus the mean of the two non-matching judges on the same answer, in percentage points with 95\% cluster-bootstrap CIs. Avoided-claim flag $\Delta$ is omitted when the slice has too few avoided-claim answers by construction.}",
            r"\label{tab:behavior-paired-sensitivity}",
            r"\end{table}",
            "",
        ]
    )
    return "\n".join(lines)


(OUT_DIR / "behavior_paired_sensitivity.tex").write_text(make_tex(), encoding="utf-8")

print("Behavior-sliced paired sensitivities (validated records)")
for name, data in report["slices"].items():
    neg_ok = data["n_avoided"] >= MIN_NEG_FOR_TABLE
    print(
        f"{name:36s} n={data['n_answers']:3d} "
        f"recall={fmt_stat(data['recall_delta']):24s} "
        f"avoided={fmt_stat(data['avoided_claim_flag_delta'], allow=neg_ok):24s} "
        f"all={fmt_stat(data['all_answer_flag_delta'])}"
    )
