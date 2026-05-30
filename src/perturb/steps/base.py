"""Step abstraction.

Default contract: a step transforms one CoreRecord → one CoreRecord (or None to drop).
Steps that need to operate on the raw stream (e.g. filter, which samples + stratifies)
override `run_stream`.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Iterable, Iterator

from ..providers.base import LLMProvider
from ..schemas import CoreRecord
from ..trace import TraceWriter


@dataclass
class StepContext:
    run_id: str
    provider: LLMProvider | None
    trace: TraceWriter | None
    options: dict


class Step(ABC):
    name: str = ""
    requires_llm: bool = False

    @abstractmethod
    def run_record(self, record: CoreRecord, ctx: StepContext) -> CoreRecord | None:
        """Transform a single record. Return None to drop it from the output stream."""
        raise NotImplementedError

    def run_stream(
        self, records: Iterable[dict], ctx: StepContext
    ) -> Iterator[CoreRecord]:
        """Default: parse each dict as CoreRecord and apply run_record."""
        for raw in records:
            record = CoreRecord.model_validate(raw)
            out = self.run_record(record, ctx)
            if out is not None:
                yield out

    def finalize(self, ctx: StepContext) -> None:
        """Optional hook after all records processed."""
        return None
