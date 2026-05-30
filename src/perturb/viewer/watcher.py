"""Filesystem watcher → in-process pub/sub. Browser subscribers get SSE events
the moment a step writes a new line or a new run dir appears."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

from watchfiles import Change, awatch

from ..config import PATHS


@dataclass
class FSEvent:
    kind: str  # "run" | "step" | "trace"
    run_id: str | None
    path: str
    change: str  # "added" | "modified" | "deleted"


_CHANGE_NAMES = {Change.added: "added", Change.modified: "modified", Change.deleted: "deleted"}


class Broadcaster:
    """Fan-out of FSEvents to N subscribers via asyncio.Queue."""

    def __init__(self) -> None:
        self._subs: set[asyncio.Queue[FSEvent]] = set()
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()

    def subscribe(self) -> asyncio.Queue[FSEvent]:
        q: asyncio.Queue[FSEvent] = asyncio.Queue(maxsize=256)
        self._subs.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[FSEvent]) -> None:
        self._subs.discard(q)

    async def _publish(self, ev: FSEvent) -> None:
        for q in list(self._subs):
            try:
                q.put_nowait(ev)
            except asyncio.QueueFull:
                # Drop oldest for slow consumers.
                try:
                    q.get_nowait()
                    q.put_nowait(ev)
                except Exception:  # noqa: BLE001
                    pass

    async def start(self) -> None:
        if self._task is not None:
            return
        # Ensure roots exist so watchfiles doesn't error on cold start.
        PATHS.ensure()
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _run(self) -> None:
        watch_paths = (str(PATHS.runs), str(PATHS.traces))
        async for changes in awatch(*watch_paths, recursive=True, stop_event=self._stop):
            for change, raw_path in changes:
                ev = _classify(Path(raw_path), change)
                if ev is not None:
                    await self._publish(ev)


def _classify(path: Path, change: Change) -> FSEvent | None:
    change_name = _CHANGE_NAMES.get(change, "modified")
    try:
        rel = path.relative_to(PATHS.runs)
        run_id = rel.parts[0] if rel.parts else None
        return FSEvent(kind="step", run_id=run_id, path=str(path), change=change_name)
    except ValueError:
        pass
    try:
        rel = path.relative_to(PATHS.traces)
        run_id = rel.parts[0] if rel.parts else None
        return FSEvent(kind="trace", run_id=run_id, path=str(path), change=change_name)
    except ValueError:
        pass
    return None


# Singleton instance the app uses.
broadcaster = Broadcaster()
