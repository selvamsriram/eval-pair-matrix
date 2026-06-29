import json
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parent
DATA = ROOT.parent / "data" / "exp" / "3provider_300.jsonl"
OUT = ROOT / "figures"

TYPE_LABELS = {
    "entity_substitution": "entity",
    "numerical_shift": "numerical",
    "causal_change": "causal",
    "temporal_shift": "temporal",
    "relation_inversion": "relation",
    "negation_modality_change": "neg/mod",
    "negation_modality": "neg/mod",
    "location_change": "location",
    "ranking_flip": "ranking",
    "affiliation_change": "affiliation",
}

PROVIDER_LABELS = {
    "azure-gpt": "GPT",
    "openai": "GPT",
    "gpt": "GPT",
    "grok": "Grok",
    "gemini": "Gemini",
}

COLORS = {
    "validated": "#54A24B",
    "diagnostic": "#E45756",
    "grid": "#D8DEE9",
    "text": "#2E3440",
}


def load_records():
    with DATA.open() as f:
        return [json.loads(line) for line in f if line.strip()]


def short_type(record):
    return TYPE_LABELS.get(record.get("perturbation_type"), record.get("perturbation_type", "other"))


def provider(record):
    raw = ((record.get("generators") or {}).get("perturb") or {}).get("provider")
    return PROVIDER_LABELS.get(raw, raw or "unknown")


def is_validated(record):
    return (record.get("pipeline_state") or {}).get("validate") == "ok"


def main():
    records = load_records()
    type_counts = Counter(short_type(r) for r in records)
    diagnostic_counts = Counter(short_type(r) for r in records if not is_validated(r))
    provider_type = defaultdict(Counter)
    provider_counts = Counter()

    for record in records:
        p = provider(record)
        t = short_type(record)
        provider_counts[p] += 1
        provider_type[p][t] += 1

    type_order = [
        "entity",
        "numerical",
        "causal",
        "temporal",
        "relation",
        "neg/mod",
        "location",
        "ranking",
        "affiliation",
    ]
    provider_order = ["GPT", "Grok", "Gemini"]

    plt.rcParams.update(
        {
            "font.size": 8,
            "axes.titlesize": 9,
            "axes.labelsize": 8,
            "xtick.labelsize": 7,
            "ytick.labelsize": 7,
            "legend.fontsize": 7,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )

    fig, axes = plt.subplots(
        1,
        2,
        figsize=(7.4, 3.15),
        gridspec_kw={"width_ratios": [1.28, 1.0], "wspace": 0.25},
    )

    ax = axes[0]
    y = np.arange(len(type_order))
    diagnostic = np.array([diagnostic_counts[t] for t in type_order])
    validated = np.array([type_counts[t] - diagnostic_counts[t] for t in type_order])
    totals = validated + diagnostic

    ax.barh(y, validated, color=COLORS["validated"], label="validated")
    ax.barh(y, diagnostic, left=validated, color=COLORS["diagnostic"], label="diagnostic")
    ax.set_yticks(y, type_order)
    ax.invert_yaxis()
    ax.set_xlabel("records")
    ax.set_title("(a) Type mix (validated/diagnostic)")
    ax.set_xlim(0, max(totals) + 14)
    ax.grid(axis="x", color=COLORS["grid"], linewidth=0.6, alpha=0.7)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, ncol=2, loc="lower right")

    for yi, total, valid, fail in zip(y, totals, validated, diagnostic):
        label = f"{int(valid)}/{int(fail)}"
        ax.text(total + 1.5, yi, label, va="center", color=COLORS["text"], fontsize=7)

    ax = axes[1]
    matrix = np.array([[provider_type[p][t] for t in type_order] for p in provider_order])
    im = ax.imshow(matrix, cmap="YlOrBr", aspect="auto")
    ax.set_title("(b) Selected perturber by type")
    ax.set_xticks(np.arange(len(type_order)), type_order, rotation=38, ha="right")
    ax.set_yticks(
        np.arange(len(provider_order)),
        [f"{p} (n={provider_counts[p]})" for p in provider_order],
    )
    ax.tick_params(axis="both", length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_xticks(np.arange(-0.5, len(type_order), 1), minor=True)
    ax.set_yticks(np.arange(-0.5, len(provider_order), 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=1.0)

    max_value = matrix.max()
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            value = int(matrix[i, j])
            if value == 0:
                continue
            color = "white" if value > max_value * 0.58 else COLORS["text"]
            ax.text(j, i, str(value), ha="center", va="center", fontsize=7, color=color)

    cbar = fig.colorbar(im, ax=ax, fraction=0.045, pad=0.02)
    cbar.set_label("records")

    OUT.mkdir(exist_ok=True)
    fig.savefig(OUT / "dataset_composition_by_type.pdf", bbox_inches="tight", pad_inches=0.035)
    fig.savefig(OUT / "dataset_composition_by_type.png", dpi=240, bbox_inches="tight", pad_inches=0.035)
    plt.close(fig)


if __name__ == "__main__":
    main()
