"""Per-LLM-call trace events. The future trace viewer reads these JSONL files."""
from __future__ import annotations

import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .io import append_jsonl


@dataclass
class TraceEvent:
    event_id: str
    run_id: str
    step: str
    core_id: str | None
    model: str
    provider: str
    started_at: float
    ended_at: float
    latency_ms: int
    system_prompt: str | None
    user_prompt: str
    raw_response: str | None
    parsed_output: Any
    input_tokens: int | None
    output_tokens: int | None
    error: str | None = None
    metadata: dict = field(default_factory=dict)


class TraceWriter:
    """Append-only JSONL writer for a specific run+step."""

    def __init__(self, run_id: str, step: str, path: Path) -> None:
        self.run_id = run_id
        self.step = step
        self.path = path

    @contextmanager
    def call(
        self,
        *,
        core_id: str | None,
        provider: str,
        model: str,
        system_prompt: str | None,
        user_prompt: str,
        metadata: dict | None = None,
    ):
        """Use as a context manager around an LLM call. Returns a mutable dict the caller fills in."""
        started = time.time()
        event_id = uuid.uuid4().hex
        slot: dict[str, Any] = {
            "raw_response": None,
            "parsed_output": None,
            "input_tokens": None,
            "output_tokens": None,
            "error": None,
        }
        try:
            yield slot
        except Exception as exc:
            slot["error"] = f"{type(exc).__name__}: {exc}"
            self._flush(event_id, core_id, provider, model, system_prompt, user_prompt, started, slot, metadata)
            raise
        self._flush(event_id, core_id, provider, model, system_prompt, user_prompt, started, slot, metadata)

    def _flush(
        self,
        event_id: str,
        core_id: str | None,
        provider: str,
        model: str,
        system_prompt: str | None,
        user_prompt: str,
        started: float,
        slot: dict,
        metadata: dict | None,
    ) -> None:
        ended = time.time()
        event = TraceEvent(
            event_id=event_id,
            run_id=self.run_id,
            step=self.step,
            core_id=core_id,
            model=model,
            provider=provider,
            started_at=started,
            ended_at=ended,
            latency_ms=int((ended - started) * 1000),
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            raw_response=slot.get("raw_response"),
            parsed_output=slot.get("parsed_output"),
            input_tokens=slot.get("input_tokens"),
            output_tokens=slot.get("output_tokens"),
            error=slot.get("error"),
            metadata=metadata or {},
        )
        append_jsonl(self.path, event.__dict__)
