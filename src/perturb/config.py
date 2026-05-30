"""Environment + path resolution. All paths are relative to the repo root unless overridden."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_REPO_ROOT / ".env")


@dataclass(frozen=True)
class Paths:
    root: Path
    data: Path
    raw: Path
    runs: Path
    traces: Path
    cache: Path
    reports: Path

    @classmethod
    def default(cls) -> "Paths":
        root = _REPO_ROOT
        data = root / "data"
        return cls(
            root=root,
            data=data,
            raw=data / "raw",
            runs=data / "runs",
            traces=data / "traces",
            cache=data / "cache",
            reports=root / "reports",
        )

    def ensure(self) -> None:
        for p in (self.raw, self.runs, self.traces, self.cache, self.reports):
            p.mkdir(parents=True, exist_ok=True)


PATHS = Paths.default()


def env(key: str, default: str | None = None) -> str | None:
    return os.environ.get(key, default)


def require_env(key: str) -> str:
    val = os.environ.get(key)
    if not val:
        raise RuntimeError(f"Missing required env var: {key}. Set it in .env.")
    return val
