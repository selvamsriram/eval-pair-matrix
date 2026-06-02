"""Run directory layout. Every step reads and writes inside data/runs/<run_id>/."""
from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

import orjson

from .config import PATHS

# Canonical step order. New steps register here.
STEP_ORDER: list[str] = [
    "filter",
    "perturb",
    "validate",
    "generate",
    "label_eval",
    "judge",
]

STEP_FILES: dict[str, str] = {name: f"{i + 1:02d}_{name}.jsonl" for i, name in enumerate(STEP_ORDER)}


@dataclass(frozen=True)
class Run:
    run_id: str
    dir: Path

    @property
    def manifest_path(self) -> Path:
        return self.dir / "manifest.json"

    def step_path(self, step: str) -> Path:
        if step not in STEP_FILES:
            raise ValueError(f"Unknown step '{step}'. Known: {list(STEP_FILES)}")
        return self.dir / STEP_FILES[step]

    def trace_path(self, step: str) -> Path:
        return PATHS.traces / self.run_id / f"{step}.jsonl"

    def prev_step(self, step: str) -> str | None:
        idx = STEP_ORDER.index(step)
        return STEP_ORDER[idx - 1] if idx > 0 else None

    def input_path_for(self, step: str) -> Path | None:
        """Default input for a step = previous step's output. None for the first step."""
        prev = self.prev_step(step)
        return self.step_path(prev) if prev else None

    def read_manifest(self) -> dict:
        if not self.manifest_path.exists():
            return {}
        return orjson.loads(self.manifest_path.read_bytes())

    def update_manifest(self, **kv) -> None:
        m = self.read_manifest()
        m.update(kv)
        m.setdefault("created_at", int(time.time()))
        m["updated_at"] = int(time.time())
        self.manifest_path.write_bytes(orjson.dumps(m, option=orjson.OPT_INDENT_2))


def new_run(name: str | None = None) -> Run:
    PATHS.ensure()
    ts = time.strftime("%Y%m%d-%H%M%S")
    run_id = f"{ts}-{name}" if name else ts
    run_dir = PATHS.runs / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    run = Run(run_id=run_id, dir=run_dir)
    run.update_manifest(run_id=run_id, name=name or "")
    return run


def open_run(run_id: str) -> Run:
    run_dir = PATHS.runs / run_id
    if not run_dir.is_dir():
        raise FileNotFoundError(
            f"Run '{run_id}' not found at {run_dir}. Use `perturb runs ls` to list."
        )
    return Run(run_id=run_id, dir=run_dir)


def list_runs() -> list[Run]:
    if not PATHS.runs.exists():
        return []
    return sorted(
        (Run(run_id=d.name, dir=d) for d in PATHS.runs.iterdir() if d.is_dir()),
        key=lambda r: r.run_id,
        reverse=True,
    )
