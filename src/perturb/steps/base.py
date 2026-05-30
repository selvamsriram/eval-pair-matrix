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
        """Default: parse each dict as CoreRecord and apply run_record.

        Per-record safety net: any unexpected exception is caught and surfaced as a
        failed:unexpected:<type>:<msg> label so one bad record can't kill the whole
        step (and discard the work already written to .tmp).
        """
        for raw in records:
            try:
                record = CoreRecord.model_validate(raw)
                out = self.run_record(record, ctx)
            except Exception as exc:  # noqa: BLE001 — last-resort safety net
                try:
                    record = CoreRecord.model_validate(raw)
                except Exception:  # noqa: BLE001
                    cid = (raw.get("core_id") if isinstance(raw, dict) else None) or "unknown"
                    record = CoreRecord(core_id=cid, garage_sample_id="", question="")
                msg = f"{type(exc).__name__}: {exc}"[:240]
                record.pipeline_state[self.name] = f"failed:unexpected:{msg}"
                out = record
            if out is not None:
                yield out

    def finalize(self, ctx: StepContext) -> None:
        """Optional hook after all records processed."""
        return None
