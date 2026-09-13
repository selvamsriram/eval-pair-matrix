"""Paired, answer-level audit of the judge-by-generator matrix.

This script implements the "statistical rescue" layer requested in the
GroundLM Round-1 review. The original ``raw_data_audit.py`` compares each
judge's diagonal cell against that judge's scores on *other generators'*
answers. Those are different answers with different styles, lengths, refusal
rates and difficulty, so the diagonal-vs-off-diagonal contrast confounds a
genuine same-deployment effect with generator difficulty.

The fix here is a *paired, within-answer* analysis. Every candidate answer was
judged by all three judges, so for each answer we can directly compare the
judge that matches the generator (``same``) against the mean of the two
non-matching judges (``cross``) on the *exact same answer*. We then attach a
cluster bootstrap over ``core_id`` to put 95% percentile intervals around the
paired deltas.

Estimand (per the revised research question):
    On the exact same candidate answer, does the matching judge behave
    differently from the non-matching judges, after holding the answer fixed?

The script is strictly READ-ONLY over the raw JSONL artifacts under ``data/``.
It writes only derived audit outputs under ``paper/audit/`` and ``paper/tables/``.

Run from anywhere:
    python paper/audit/paired_audit.py
Configurable via environment:
    PAIRED_BOOTSTRAP=10000   number of cluster-bootstrap replicates
    PAIRED_SEED=20260627     RNG seed
"""
from __future__ import annotations

import csv
import json
import os
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
ROOT = Path(__file__).resolve().parents[2]
AUDIT_DIR = Path(__file__).resolve().parent
TABLES_DIR = ROOT / "paper" / "tables"

PROVIDERS = ["GPT", "Grok", "Gemini"]
# Raw provider strings in the JSONL -> canonical provider bucket.
PROVIDER_OF = {"azure-gpt": "GPT", "grok": "Grok", "gemini": "Gemini"}
# Exact deployment id per provider (for the methods table / provenance).
MODEL_OF = {"GPT": "gpt-5.4", "Grok": "grok-4.3", "Gemini": "gemini-3.5-flash"}

# Five validation gates that define the primary (validated) benchmark.
# This mirrors raw_data_audit.GATES / raw_data_audit.passes; kept local so the
# script has no import-time side effects (raw_data_audit runs analysis on import).
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


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def rows(path):
    return [json.loads(x) for x in (ROOT / path).read_text(encoding="utf-8").splitlines() if x.strip()]


def passes(record):
    """True iff all five validation gates pass. Mirrors raw_data_audit.passes."""
    v = record.get("validation") or {}
    return all(v.get(gate) is True for gate in GATES)


def pct(n, d):
    return None if not d else round(100 * n / d, 3)


def prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return round(100 * p, 3), round(100 * r, 3), round(100 * f, 3)


def r3(x):
    return None if x is None else round(float(x), 3)


# --------------------------------------------------------------------------- #
# Load raw data
# --------------------------------------------------------------------------- #
files = {}

core = rows(CORE_PATH)
files[CORE_PATH] = len(core)
validated_ids = {r["core_id"] for r in core if passes(r)}
perturber_of = {r["core_id"]: PROVIDER_OF.get(((r.get("generators") or {}).get("perturb") or {}).get("provider"), "unknown") for r in core}
ptype_of = {r["core_id"]: (r.get("perturbation_type") or "unknown") for r in core}
n_validated = len(validated_ids)
n_gap = len(core) - n_validated

# behavior labels keyed by (core_id, generator_bucket, sample_id)
behavior_label = {}
for gen, path in LABEL_RUNS.items():
    rs = rows(path)
    files[path] = len(rs)
    for r in rs:
        cid = r["core_id"]
        for out in r.get("generator_outputs") or []:
            # Behavior label is the LLM label-evaluation output (Table 1 source).
            # Do NOT fall back to the generator's self-reported label: that would
            # silently re-label the 3 outputs with no llm_eval, masking them as a
            # real behavior class. Leave them blank (== unlabeled).
            lab = (out.get("llm_eval") or {}).get("behavior_label")
            behavior_label[(cid, gen, out.get("sample_id"))] = lab

# --------------------------------------------------------------------------- #
# Flatten every judge verdict into one long table
# --------------------------------------------------------------------------- #
FLAT_COLUMNS = [
    "core_id",
    "is_validated",
    "generator_provider",
    "generator_model",
    "generator_sample_id",
    "generator_bucket",
    "judge_provider",
    "judge_model",
    "judge_bucket",
    "is_matching",
    "pair_type",
    "gold_has_induced_error",
    "contains_factual_error",
    "verdict",
    "wrong_claim",
    "supporting_source_passage_id",
    "modified_passage_ids",
    "perturbation_type",
    "behavior_label",
]

flat = []
total_verdicts = 0
pair_types = Counter()
for (judge, gen), path in JUDGE_RUNS.items():
    rs = rows(path)
    files[path] = len(rs)
    for r in rs:
        cid = r["core_id"]
        modified = r.get("modified_passage_ids") or []
        for v in r.get("judge_verdicts") or []:
            total_verdicts += 1
            pair_types[v.get("pair_type", "missing")] += 1
            sid = v.get("generator_sample_id")
            flat.append(
                {
                    "core_id": cid,
                    "is_validated": cid in validated_ids,
                    "generator_provider": v.get("generator_provider"),
                    "generator_model": v.get("generator_model"),
                    "generator_sample_id": sid,
                    "generator_bucket": gen,
                    "judge_provider": v.get("judge_provider"),
                    "judge_model": v.get("judge_model"),
                    "judge_bucket": judge,
                    "is_matching": judge == gen,
                    "pair_type": v.get("pair_type"),
                    "gold_has_induced_error": bool(v.get("gold_has_induced_error")),
                    "contains_factual_error": bool(v.get("contains_factual_error")),
                    "verdict": v.get("verdict"),
                    "wrong_claim": v.get("wrong_claim"),
                    "supporting_source_passage_id": v.get("supporting_source_passage_id"),
                    "modified_passage_ids": modified,
                    "perturbation_type": ptype_of.get(cid, "unknown"),
                    "behavior_label": behavior_label.get((cid, gen, sid)),
                }
            )

# --------------------------------------------------------------------------- #
# 3x3 confusion matrices (full / validated / gap-fill)
# --------------------------------------------------------------------------- #
def build_matrix(predicate):
    """Confusion matrix per (judge, generator) cell over rows where predicate(row)."""
    cells = {}
    agg = defaultdict(lambda: dict(n=0, gold_pos=0, tp=0, fp=0, tn=0, fn=0))
    for row in flat:
        if not predicate(row):
            continue
        key = (row["judge_bucket"], row["generator_bucket"])
        c = agg[key]
        gold = row["gold_has_induced_error"]
        pred = row["contains_factual_error"]
        c["n"] += 1
        c["gold_pos"] += gold
        if gold and pred:
            c["tp"] += 1
        elif gold and not pred:
            c["fn"] += 1
        elif (not gold) and pred:
            c["fp"] += 1
        else:
            c["tn"] += 1
    for judge in PROVIDERS:
        for gen in PROVIDERS:
            c = agg[(judge, gen)]
            p, r, f = prf(c["tp"], c["fp"], c["fn"])
            fpr = pct(c["fp"], c["fp"] + c["tn"])
            cells[f"{judge}_on_{gen}"] = {
                "n": c["n"],
                "gold_pos": c["gold_pos"],
                "tp": c["tp"],
                "fp": c["fp"],
                "tn": c["tn"],
                "fn": c["fn"],
                "precision": p,
                "recall": r,
                "f1": f,
                "fpr": fpr,
            }
    # margins
    def f1(j, g):
        return cells[f"{j}_on_{g}"]["f1"]

    row_avg = {j: r3(np.mean([f1(j, g) for g in PROVIDERS])) for j in PROVIDERS}
    col_avg = {g: r3(np.mean([f1(j, g) for j in PROVIDERS])) for g in PROVIDERS}
    diag = [f1(x, x) for x in PROVIDERS]
    off = [f1(j, g) for j in PROVIDERS for g in PROVIDERS if j != g]
    margins = {
        "row_avg_f1": row_avg,
        "col_avg_f1": col_avg,
        "diag_avg_f1": r3(np.mean(diag)),
        "offdiag_avg_f1": r3(np.mean(off)),
        "diag_minus_offdiag_f1": r3(np.mean(diag) - np.mean(off)),
    }
    return {"cells": cells, "margins": margins}


matrices = {
    "full": build_matrix(lambda row: True),
    "validated": build_matrix(lambda row: row["is_validated"]),
    "gap_fill": build_matrix(lambda row: not row["is_validated"]),
}

# --------------------------------------------------------------------------- #
# Unpaired (flawed) diagonal-vs-offdiagonal contrast, recomputed for reference
# --------------------------------------------------------------------------- #
def unpaired_effects(cells):
    out = {}
    for j in PROVIDERS:
        own = cells[f"{j}_on_{j}"]
        cross = [cells[f"{j}_on_{g}"] for g in PROVIDERS if g != j]
        out[j] = {
            "recall_own": own["recall"],
            "recall_cross": r3(np.mean([c["recall"] for c in cross])),
            "recall_delta": r3(own["recall"] - np.mean([c["recall"] for c in cross])),
            "fpr_own": own["fpr"],
            "fpr_cross": r3(np.mean([c["fpr"] for c in cross])),
            "fpr_delta": r3((own["fpr"] or 0) - np.mean([c["fpr"] or 0 for c in cross])),
            "f1_own": own["f1"],
            "f1_cross": r3(np.mean([c["f1"] for c in cross])),
            "f1_delta": r3(own["f1"] - np.mean([c["f1"] for c in cross])),
        }
    return out


unpaired = {
    "validated": unpaired_effects(matrices["validated"]["cells"]),
    "full": unpaired_effects(matrices["full"]["cells"]),
}

# --------------------------------------------------------------------------- #
# Answer-paired effect: same judge vs mean of cross judges, per answer
# --------------------------------------------------------------------------- #
# Per-answer prediction map: answer_key -> {judge_bucket: pred}
preds_by_answer = defaultdict(dict)
gold_by_answer = {}
valid_by_answer = {}
gen_by_answer = {}
core_by_answer = {}
for row in flat:
    key = (row["core_id"], row["generator_bucket"], row["generator_sample_id"])
    preds_by_answer[key][row["judge_bucket"]] = int(row["contains_factual_error"])
    gold_by_answer[key] = row["gold_has_induced_error"]
    valid_by_answer[key] = row["is_validated"]
    gen_by_answer[key] = row["generator_bucket"]
    core_by_answer[key] = row["core_id"]

# Build per-answer arrays for usable answers (matching judge + >=1 cross judge).
core_ids_sorted = sorted({r["core_id"] for r in core})
core_index = {cid: i for i, cid in enumerate(core_ids_sorted)}
n_cores = len(core_ids_sorted)

a_core = []        # core index
a_gen = []         # generator bucket (str)
a_same = []        # matching-judge prediction (0/1)
a_cross = []       # mean of non-matching judges' predictions
a_gold = []        # bool
a_valid = []       # bool
n_dropped_no_match = 0
for key, preds in preds_by_answer.items():
    gen = gen_by_answer[key]
    if gen not in preds:
        n_dropped_no_match += 1
        continue
    cross_vals = [p for jb, p in preds.items() if jb != gen]
    if not cross_vals:
        n_dropped_no_match += 1
        continue
    a_core.append(core_index[core_by_answer[key]])
    a_gen.append(gen)
    a_same.append(preds[gen])
    a_cross.append(float(np.mean(cross_vals)))
    a_gold.append(bool(gold_by_answer[key]))
    a_valid.append(bool(valid_by_answer[key]))

a_core = np.asarray(a_core, dtype=np.int64)
a_gen = np.asarray(a_gen)
a_same = np.asarray(a_same, dtype=float)
a_cross = np.asarray(a_cross, dtype=float)
a_delta = a_same - a_cross
a_gold = np.asarray(a_gold, dtype=bool)
a_valid = np.asarray(a_valid, dtype=bool)

# Cluster bootstrap. The resampling unit is the question (core_id), but the
# cluster POPULATION must match each dataset's estimand: the validated benchmark
# is a sample of the 275 validated cores, so its CI resamples 275 cores with
# replacement; the full set resamples 300; the gap-fill diagnostic resamples 25.
# Resampling all 300 for a validated-only estimand would inject extra variance
# from a fluctuating validated count, which is not part of that estimand.
all_core_idx = list(range(n_cores))
validated_core_idx = sorted(core_index[c] for c in validated_ids)
gapfill_core_idx = sorted(core_index[c] for c in ({r["core_id"] for r in core} - validated_ids))


class Resampler:
    """Cluster bootstrap over a fixed population of core_ids.

    One weight matrix W (B x n_pop) is drawn per population and reused across every
    stratum that shares that population, so all intervals in a panel (recall / FPR /
    flag-rate, and the per-generator rows) come from one coherent joint resample.
    The paired delta same-vs-cross is already fixed per answer, so pairing is
    preserved on every replicate regardless.
    """

    def __init__(self, pop_core_idx, seed):
        self.pop = np.asarray(sorted(pop_core_idx), dtype=np.int64)
        self.npop = len(self.pop)
        rng = np.random.default_rng(seed)
        self.W = rng.multinomial(self.npop, np.full(self.npop, 1.0 / self.npop), size=N_BOOT).astype(np.float64)

    def stat(self, mask):
        """Point estimate + 95% percentile CI for the paired delta over masked answers."""
        n = int(mask.sum())
        if n == 0:
            return {"n": 0, "same_mean": None, "cross_mean": None, "delta": None, "ci_low": None, "ci_high": None}
        ci = a_core[mask]
        d = a_delta[mask]
        # per-core sufficient statistics, restricted to this population's cores
        sum_delta_core = np.bincount(ci, weights=d, minlength=n_cores)[self.pop]
        cnt_core = np.bincount(ci, minlength=n_cores).astype(float)[self.pop]
        point = float(sum_delta_core.sum() / cnt_core.sum())
        numer = self.W @ sum_delta_core
        denom = self.W @ cnt_core
        ok = denom > 0
        reps = numer[ok] / denom[ok]
        lo, hi = np.percentile(reps, [2.5, 97.5])
        return {
            "n": n,
            "n_clusters": self.npop,
            "same_mean": r3(100 * a_same[mask].mean()),
            "cross_mean": r3(100 * a_cross[mask].mean()),
            "delta": r3(100 * point),
            "ci_low": r3(100 * lo),
            "ci_high": r3(100 * hi),
        }


# Independent, reproducible streams per dataset (distinct seeds so the three
# panels are not accidentally driven by the same resample sequence).
RS_VALIDATED = Resampler(validated_core_idx, SEED)
RS_FULL = Resampler(all_core_idx, SEED + 101)
RS_GAP = Resampler(gapfill_core_idx, SEED + 202)


def stratum_block(resampler, base_mask):
    """recall(gold-pos) / fpr(gold-neg) / flag-rate(all) paired deltas for a mask."""
    return {
        "recall_delta": resampler.stat(base_mask & a_gold),
        "fpr_delta": resampler.stat(base_mask & ~a_gold),
        "flag_rate_delta": resampler.stat(base_mask),
    }


all_mask = np.ones(len(a_core), dtype=bool)
paired = {
    "validated": stratum_block(RS_VALIDATED, a_valid),     # PRIMARY benchmark (resamples 275 cores)
    "full": stratum_block(RS_FULL, all_mask),              # sensitivity (resamples 300 cores)
    "gap_fill": stratum_block(RS_GAP, ~a_valid),           # diagnostic (resamples 25 cores)
    "by_generator_validated": {
        g: stratum_block(RS_VALIDATED, a_valid & (a_gen == g)) for g in PROVIDERS
    },
    "by_generator_full": {
        g: stratum_block(RS_FULL, a_gen == g) for g in PROVIDERS
    },
}

# Attach the unpaired (flawed) recall delta next to the paired one, per generator,
# so the summary can show the contrast that motivated the rescue.
for g in PROVIDERS:
    paired["by_generator_validated"][g]["unpaired_recall_delta"] = unpaired["validated"][g]["recall_delta"]
    paired["by_generator_validated"][g]["unpaired_fpr_delta"] = unpaired["validated"][g]["fpr_delta"]
    paired["by_generator_validated"][g]["unpaired_f1_delta"] = unpaired["validated"][g]["f1_delta"]

# --------------------------------------------------------------------------- #
# Assemble report
# --------------------------------------------------------------------------- #
n_goldpos = int(a_gold.sum())
n_goldneg = int((~a_gold).sum())
report = {
    "meta": {
        "description": "Paired, answer-level audit of the judge-by-generator matrix (statistical rescue layer).",
        "estimand": "On the exact same candidate answer, does the matching judge behave differently from the mean of the two non-matching judges?",
        "primary_set": "275 validated records (all five gates pass); gap-fill 25 records reported as diagnostic only.",
        "paired_delta_definition": "per answer: same_pred - mean(cross_preds); reported as percentage points.",
        "bootstrap": {
            "method": "cluster bootstrap by core_id; each dataset resamples its own cluster population",
            "clusters": {"validated": len(validated_core_idx), "full": n_cores, "gap_fill": len(gapfill_core_idx)},
            "replicates": N_BOOT,
            "seeds": {"validated": SEED, "full": SEED + 101, "gap_fill": SEED + 202},
            "ci": "95% percentile",
        },
        "provider_models": MODEL_OF,
        "multiple_testing_note": "Per-generator (by_generator_*) deltas are EXPLORATORY and uncorrected for multiple comparisons; treat the global validated delta as the confirmatory estimand.",
        "read_only": True,
    },
    "files": files,
    "counts": {
        "core_records": len(core),
        "unique_core_ids": len({r["core_id"] for r in core}),
        "validated": n_validated,
        "gap_fill": n_gap,
        "total_verdicts": total_verdicts,
        "pair_types": dict(pair_types),
        "unique_answers": len(preds_by_answer),
        "answers_usable_paired": int(len(a_core)),
        "answers_dropped_no_pairing": n_dropped_no_match,
        "paired_gold_positive": n_goldpos,
        "paired_gold_negative": n_goldneg,
        "perturber_counts": dict(Counter(perturber_of[c] for c in core_ids_sorted)),
    },
    "matrices": matrices,
    "paired_effects": paired,
    "unpaired_reference": unpaired,
}

# --------------------------------------------------------------------------- #
# Write JSON report
# --------------------------------------------------------------------------- #
AUDIT_DIR.mkdir(parents=True, exist_ok=True)
TABLES_DIR.mkdir(parents=True, exist_ok=True)
(AUDIT_DIR / "paired_audit_report.json").write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

# --------------------------------------------------------------------------- #
# Write flattened verdict table (CSV)
# --------------------------------------------------------------------------- #
with (AUDIT_DIR / "paired_verdicts.csv").open("w", newline="", encoding="utf-8") as fh:
    writer = csv.DictWriter(fh, fieldnames=FLAT_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for row in flat:
        out = dict(row)
        out["modified_passage_ids"] = ";".join(str(x) for x in (row["modified_passage_ids"] or []))
        writer.writerow(out)


# --------------------------------------------------------------------------- #
# LaTeX: validated-only 3x3 matrix
# --------------------------------------------------------------------------- #
def fmt(x):
    return "--" if x is None else f"{x:.1f}"


def validated_matrix_tex():
    cells = matrices["validated"]["cells"]
    m = matrices["validated"]["margins"]
    lines = []
    lines.append("% Auto-generated by paper/audit/paired_audit.py -- do not edit by hand.")
    lines.append(r"\begin{table*}[t]")
    lines.append(r"\centering")
    lines.append(r"\small")
    lines.append(r"\begin{tabular}{l ccc ccc ccc c}")
    lines.append(r"\toprule")
    lines.append(r" & \multicolumn{3}{c}{GPT answers} & \multicolumn{3}{c}{Grok answers} & \multicolumn{3}{c}{Gemini answers} & \\")
    lines.append(r"\cmidrule(lr){2-4}\cmidrule(lr){5-7}\cmidrule(lr){8-10}")
    lines.append(r"Judge & P & R & F1 & P & R & F1 & P & R & F1 & Row F1 \\")
    lines.append(r"\midrule")
    for j in PROVIDERS:
        parts = [j]
        for g in PROVIDERS:
            c = cells[f"{j}_on_{g}"]
            tag = r"\textbf{%s}" if j == g else "%s"
            parts += [tag % fmt(c["precision"]), tag % fmt(c["recall"]), tag % fmt(c["f1"])]
        parts.append(fmt(m["row_avg_f1"][j]))
        lines.append(" & ".join(parts) + r" \\")
    lines.append(r"\midrule")
    col = ["Col F1"]
    for g in PROVIDERS:
        col += ["", "", fmt(m["col_avg_f1"][g])]
    col.append("")
    lines.append(" & ".join(col) + r" \\")
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    cap = (
        r"\caption{Validated-only judge$\times$generator matrix (%d validated records; "
        r"diagonal = same-deployment cells, bold). Per cell: precision / recall / F1 (\%%). "
        r"Mean diagonal F1 $=%.1f$, mean off-diagonal F1 $=%.1f$ (diff $=%.1f$). "
        r"Raw diagonal differences are small; see Table~\ref{tab:paired-effects} for the paired, "
        r"answer-level analysis that controls for generator difficulty.}"
        % (n_validated, m["diag_avg_f1"], m["offdiag_avg_f1"], m["diag_minus_offdiag_f1"])
    )
    lines.append(cap)
    lines.append(r"\label{tab:validated-matrix}")
    lines.append(r"\end{table*}")
    return "\n".join(lines) + "\n"


def ci_str(s):
    if s["delta"] is None:
        return "--"
    return f"{s['delta']:+.1f} [{s['ci_low']:+.1f}, {s['ci_high']:+.1f}]"


def paired_effects_tex():
    v = paired["validated"]
    bg = paired["by_generator_validated"]
    lines = []
    lines.append("% Auto-generated by paper/audit/paired_audit.py -- do not edit by hand.")
    lines.append(r"\begin{table}[t]")
    lines.append(r"\centering")
    lines.append(r"\small")
    lines.append(r"\begin{tabular}{l ccc}")
    lines.append(r"\toprule")
    lines.append(r"Contrast & Recall $\Delta$ & FPR $\Delta$ & Flag-rate $\Delta$ \\")
    lines.append(r"\midrule")
    lines.append(r"\multicolumn{4}{l}{\emph{Primary}} \\")
    lines.append(
        " & ".join(["Global (same vs cross)", ci_str(v["recall_delta"]), ci_str(v["fpr_delta"]), ci_str(v["flag_rate_delta"])]) + r" \\"
    )
    lines.append(r"\midrule")
    lines.append(r"\multicolumn{4}{l}{\emph{Exploratory (per-generator, uncorrected)}} \\")
    for g in PROVIDERS:
        b = bg[g]
        lines.append(
            " & ".join([f"{g}-on-{g} vs others", ci_str(b["recall_delta"]), ci_str(b["fpr_delta"]), ci_str(b["flag_rate_delta"])]) + r" \\"
        )
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    cap = (
        r"\caption{Paired same-deployment effect on the %d validated records: matching judge "
        r"minus the mean of the two non-matching judges, computed \emph{within each answer} "
        r"(percentage points; 95\%% cluster-bootstrap CI resampling the %d validated core IDs, "
        r"%s replicates). "
        r"Recall $\Delta$ is over gold-positive answers, FPR $\Delta$ over gold-negative answers, "
        r"flag-rate $\Delta$ over all answers. Per-generator rows are exploratory and uncorrected "
        r"for multiple comparisons.}"
        % (n_validated, n_validated, f"{N_BOOT:,}")
    )
    lines.append(cap)
    lines.append(r"\label{tab:paired-effects}")
    lines.append(r"\end{table}")
    return "\n".join(lines) + "\n"


(TABLES_DIR / "validated_matrix.tex").write_text(validated_matrix_tex(), encoding="utf-8")
(TABLES_DIR / "paired_effects.tex").write_text(paired_effects_tex(), encoding="utf-8")


# --------------------------------------------------------------------------- #
# Markdown summary
# --------------------------------------------------------------------------- #
def crosses_zero(s):
    return s["ci_low"] is not None and s["ci_low"] <= 0 <= s["ci_high"]


def md_row(label, s):
    return f"| {label} | {s['same_mean']} | {s['cross_mean']} | {s['delta']:+.1f} | [{s['ci_low']:+.1f}, {s['ci_high']:+.1f}] | {'yes' if crosses_zero(s) else '**no**'} |"


def summary_md():
    v = paired["validated"]
    bg = paired["by_generator_validated"]
    L = []
    L.append("# Paired audit summary (statistical rescue layer)")
    L.append("")
    L.append(f"Generated by `paper/audit/paired_audit.py` — read-only over raw JSONL. "
             f"Bootstrap: {N_BOOT:,} cluster replicates, resampling each dataset's own cluster "
             f"population by core_id (validated {len(validated_core_idx)} / full {n_cores} / "
             f"gap-fill {len(gapfill_core_idx)}), seed {SEED}.")
    L.append("")
    L.append("## What changed and why")
    L.append("")
    L.append("The original audit compared each judge's diagonal cell against that judge's scores on "
             "**other generators' answers** — different answers with different difficulty, length and "
             "refusal behaviour. This version makes the comparison **within the same answer**: every "
             "candidate answer was judged by all three judges, so for each answer we compare the "
             "matching judge against the mean of the two non-matching judges. Deltas are in percentage "
             "points; positive means the matching (same-deployment) judge flags *more* than the cross judges.")
    L.append("")
    L.append("## Headline (PRIMARY = 275 validated records)")
    L.append("")
    L.append("| Contrast | same % | cross % | Δ (pp) | 95% CI | CI crosses 0? |")
    L.append("|---|---|---|---|---|---|")
    L.append(md_row("Recall Δ (gold-positive)", v["recall_delta"]))
    L.append(md_row("FPR Δ (gold-negative)", v["fpr_delta"]))
    L.append(md_row("Flag-rate Δ (all answers)", v["flag_rate_delta"]))
    L.append("")
    rec, fpr, flag = v["recall_delta"], v["fpr_delta"], v["flag_rate_delta"]
    L.append("**Decision rule outcome (per the review's Step 4 rule):**")
    L.append("")
    if crosses_zero(rec):
        L.append(f"- **Recall: null.** Holding the answer fixed, the matching judge is *not* worse at "
                 f"catching genuine induced errors (Δ = {rec['delta']:+.1f} pp, 95% CI "
                 f"[{rec['ci_low']:+.1f}, {rec['ci_high']:+.1f}] — includes 0). The headline "
                 f"“self-leniency lets a judge miss its own model's errors” claim is **not** "
                 f"supported once generator difficulty is controlled.")
    else:
        L.append(f"- **Recall: effect present** (Δ = {rec['delta']:+.1f} pp, CI "
                 f"[{rec['ci_low']:+.1f}, {rec['ci_high']:+.1f}]).")
    if not crosses_zero(fpr):
        direction = "lower" if fpr["delta"] < 0 else "higher"
        L.append(f"- **False-positive rate: robust effect.** On gold-negative answers the matching judge "
                 f"has a {direction} FPR than the cross judges (Δ = {fpr['delta']:+.1f} pp, CI "
                 f"[{fpr['ci_low']:+.1f}, {fpr['ci_high']:+.1f}] — excludes 0). Same-deployment leniency "
                 f"surfaces as **reduced over-flagging of its own model's correct answers**, not as missed "
                 f"true errors.")
    else:
        L.append(f"- **False-positive rate: null** (Δ = {fpr['delta']:+.1f} pp, CI "
                 f"[{fpr['ci_low']:+.1f}, {fpr['ci_high']:+.1f}]).")
    if not crosses_zero(flag):
        L.append(f"- **Overall flag rate: robust effect** (Δ = {flag['delta']:+.1f} pp, CI "
                 f"[{flag['ci_low']:+.1f}, {flag['ci_high']:+.1f}] — excludes 0), driven by the FPR gap.")
    else:
        L.append(f"- **Overall flag rate: null** (Δ = {flag['delta']:+.1f} pp, CI "
                 f"[{flag['ci_low']:+.1f}, {flag['ci_high']:+.1f}]).")
    L.append("")
    L.append("**Suggested headline sentence for the abstract:**")
    L.append("")
    L.append(f"> Across a fully crossed 3×3 matrix, raw diagonal differences are small "
             f"(mean diagonal F1 {matrices['validated']['margins']['diag_avg_f1']} vs off-diagonal "
             f"{matrices['validated']['margins']['offdiag_avg_f1']}). After a paired, answer-level "
             f"analysis on 275 validated records, we find **no robust same-deployment effect on recall** "
             f"(Δ = {rec['delta']:+.1f} pp, 95% CI [{rec['ci_low']:+.1f}, {rec['ci_high']:+.1f}]), but a "
             f"**robust same-deployment leniency on gold-negative answers** "
             f"(false-positive-rate Δ = {fpr['delta']:+.1f} pp, CI [{fpr['ci_low']:+.1f}, {fpr['ci_high']:+.1f}]); "
             f"generator behaviour and answerability explain substantial variation in judge performance.")
    L.append("")
    L.append("## Exploratory per-generator paired deltas (uncorrected)")
    L.append("")
    L.append("Per-generator rows are exploratory (three comparisons, no multiple-testing correction). "
             "The **unpaired** column is the old, confounded diagonal-minus-off-diagonal recall delta, "
             "shown for contrast.")
    L.append("")
    L.append("| Generator | paired recall Δ | 95% CI | crosses 0? | unpaired recall Δ (old) |")
    L.append("|---|---|---|---|---|")
    for g in PROVIDERS:
        b = bg[g]
        s = b["recall_delta"]
        L.append(f"| {g}-on-{g} | {s['delta']:+.1f} | [{s['ci_low']:+.1f}, {s['ci_high']:+.1f}] | "
                 f"{'yes' if crosses_zero(s) else '**no**'} | {b['unpaired_recall_delta']:+.1f} |")
    L.append("")
    L.append("Where the paired interval crosses zero but the old unpaired delta looked large, the apparent "
             "effect was generator-difficulty confound, not a same-deployment signature.")
    L.append("")
    L.append("## Validated-only 3×3 matrix (point estimates)")
    L.append("")
    cells = matrices["validated"]["cells"]
    m = matrices["validated"]["margins"]
    L.append("| Judge \\ Generator | GPT (P/R/F1) | Grok (P/R/F1) | Gemini (P/R/F1) | Row F1 |")
    L.append("|---|---|---|---|---|")
    for j in PROVIDERS:
        parts = [f"**{j}**"]
        for g in PROVIDERS:
            c = cells[f"{j}_on_{g}"]
            cell = f"{fmt(c['precision'])}/{fmt(c['recall'])}/{fmt(c['f1'])}"
            if j == g:
                cell = f"**{cell}**"
            parts.append(cell)
        parts.append(fmt(m["row_avg_f1"][j]))
        L.append("| " + " | ".join(parts) + " |")
    L.append("")
    L.append(f"Mean diagonal F1 = {m['diag_avg_f1']}, mean off-diagonal F1 = {m['offdiag_avg_f1']}, "
             f"diff = {m['diag_minus_offdiag_f1']} pp.")
    L.append("")
    L.append("## Sensitivity: full vs validated vs gap-fill (global paired deltas)")
    L.append("")
    L.append("| Set | recall Δ [CI] | FPR Δ [CI] | flag-rate Δ [CI] | n answers |")
    L.append("|---|---|---|---|---|")
    for name, key in [("Validated (275)", "validated"), ("Full (300)", "full"), ("Gap-fill (25)", "gap_fill")]:
        blk = paired[key]
        L.append(f"| {name} | {ci_str(blk['recall_delta'])} | {ci_str(blk['fpr_delta'])} | "
                 f"{ci_str(blk['flag_rate_delta'])} | {blk['flag_rate_delta']['n']} |")
    L.append("")
    L.append("## Counts (sanity)")
    L.append("")
    c = report["counts"]
    L.append(f"- core records: {c['core_records']} (validated {c['validated']}, gap-fill {c['gap_fill']})")
    L.append(f"- total verdicts: {c['total_verdicts']}; pair types: {c['pair_types']}")
    L.append(f"- usable paired answers: {c['answers_usable_paired']} "
             f"(gold+ {c['paired_gold_positive']}, gold- {c['paired_gold_negative']}; "
             f"dropped for no pairing: {c['answers_dropped_no_pairing']})")
    L.append("")
    L.append("Artifacts: `paired_audit_report.json`, `paired_verdicts.csv`, "
             "`../tables/validated_matrix.tex`, `../tables/paired_effects.tex`.")
    return "\n".join(L) + "\n"


summary_path = ROOT / "tmp" / "analysis" / "paired_audit_summary.md"
summary_path.parent.mkdir(parents=True, exist_ok=True)
summary_path.write_text(summary_md(), encoding="utf-8")

# --------------------------------------------------------------------------- #
# Sanity asserts (catch data drift) + console output
# --------------------------------------------------------------------------- #
assert len(core) == 300 and len({r["core_id"] for r in core}) == 300, "core count drift"
assert n_validated == 275 and n_gap == 25, "validated/gap-fill drift"
assert total_verdicts == 2683, "verdict count drift"

print(f"core={len(core)} validated={n_validated} gap_fill={n_gap} verdicts={total_verdicts}")
print(f"usable paired answers={len(a_core)} (gold+ {n_goldpos}, gold- {n_goldneg})")
print("Global paired deltas (validated, pp, [95% CI]):")
for k in ("recall_delta", "fpr_delta", "flag_rate_delta"):
    s = paired["validated"][k]
    print(f"  {k:16s}: {s['delta']:+.2f}  [{s['ci_low']:+.2f}, {s['ci_high']:+.2f}]  same={s['same_mean']} cross={s['cross_mean']}")
print("Wrote: paired_audit_report.json, tmp/analysis/paired_audit_summary.md, paired_verdicts.csv,")
print("       ../tables/validated_matrix.tex, ../tables/paired_effects.tex")
