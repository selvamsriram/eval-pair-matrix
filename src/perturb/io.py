"""JSONL streaming helpers. orjson for speed, atomic writes via .tmp swap."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, Iterator

import orjson
from pydantic import BaseModel


def read_jsonl(path: Path) -> Iterator[dict]:
    with path.open("rb") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield orjson.loads(line)


def write_jsonl(path: Path, records: Iterable[dict | BaseModel]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    n = 0
    with tmp.open("wb") as f:
        for r in records:
            if isinstance(r, BaseModel):
                payload = r.model_dump(mode="json", exclude_none=False)
            else:
                payload = r
            f.write(orjson.dumps(payload))
            f.write(b"\n")
            f.flush()
            n += 1
    tmp.replace(path)
    return n


def append_jsonl(path: Path, record: dict | BaseModel) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = record.model_dump(mode="json") if isinstance(record, BaseModel) else record
    with path.open("ab") as f:
        f.write(orjson.dumps(payload))
        f.write(b"\n")


def count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("rb") as f:
        return sum(1 for line in f if line.strip())
