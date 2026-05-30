"""GaRAGe ingestion. Pulls AmazonScience/GaRAGe from HuggingFace and normalizes to JSONL.

We keep this outside the pipeline step registry because it runs once, against the
internet, and lands in data/raw/ rather than a run dir.
"""
from __future__ import annotations

from pathlib import Path

from .config import PATHS
from .io import write_jsonl

HF_DATASET = "AmazonScience/GaRAGe"


def fetch_garage(
    *,
    split: str = "train",
    out: Path | None = None,
    limit: int | None = None,
) -> Path:
    PATHS.ensure()
    dest = out or (PATHS.raw / f"garage_{split}.jsonl")
    try:
        from datasets import load_dataset
    except ImportError as exc:
        raise RuntimeError(
            "Install the `datasets` extra (already in pyproject deps): "
            "`pip install datasets`."
        ) from exc

    ds = load_dataset(HF_DATASET, split=split)
    rows = (dict(r) for i, r in enumerate(ds) if limit is None or i < limit)
    n = write_jsonl(dest, rows)
    return dest if n > 0 else dest
