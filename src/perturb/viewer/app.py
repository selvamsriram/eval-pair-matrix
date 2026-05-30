"""FastAPI app: API + index page + SSE."""
from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path

import orjson
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, ORJSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from ..run import STEP_ORDER, open_run
from . import data
from .watcher import broadcaster


_HERE = Path(__file__).parent
_TEMPLATES = Jinja2Templates(directory=str(_HERE / "templates"))


@asynccontextmanager
async def _lifespan(_: FastAPI):
    await broadcaster.start()
    try:
        yield
    finally:
        await broadcaster.stop()


def create_app() -> FastAPI:
    app = FastAPI(
        title="perturb viewer",
        default_response_class=ORJSONResponse,
        lifespan=_lifespan,
        docs_url=None,
        redoc_url=None,
    )

    app.mount("/static", StaticFiles(directory=str(_HERE / "static")), name="static")

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        return _TEMPLATES.TemplateResponse(request, "index.html")

    @app.get("/api/runs")
    async def runs():
        return {
            "latest": (data.latest_run().run_id if data.latest_run() else None),
            "runs": data.all_runs(),
            "step_order": STEP_ORDER,
        }

    @app.get("/api/runs/{run_id}/records")
    async def records(run_id: str):
        run = _open(run_id)
        summaries = data.list_record_summaries(run)
        return {"records": [s.__dict__ for s in summaries]}

    @app.get("/api/runs/{run_id}/records/{core_id}")
    async def record_detail(run_id: str, core_id: str):
        run = _open(run_id)
        rec = data.get_record(run, core_id)
        if rec is None:
            raise HTTPException(404, detail="record not found")
        diffs = data.passage_diffs(rec)
        events = data.trace_events_for(run, core_id)
        return {"record": rec, "diffs": diffs, "trace_events": events}

    @app.get("/api/runs/{run_id}/manifest")
    async def manifest(run_id: str):
        return _open(run_id).read_manifest()

    @app.get("/api/events")
    async def events():
        return StreamingResponse(_sse(), media_type="text/event-stream", headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        })

    return app


def _open(run_id: str):
    try:
        return open_run(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(404, detail=str(exc))


async def _sse():
    """SSE stream: filesystem events + a heartbeat to keep proxies honest."""
    q = broadcaster.subscribe()
    try:
        # Send a hello so the client knows the channel is alive.
        yield _format_sse("hello", {"ok": True})
        while True:
            try:
                ev = await asyncio.wait_for(q.get(), timeout=15.0)
                yield _format_sse(
                    "fs",
                    {
                        "kind": ev.kind,
                        "run_id": ev.run_id,
                        "path": ev.path,
                        "change": ev.change,
                    },
                )
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"  # SSE comment heartbeat
    finally:
        broadcaster.unsubscribe(q)


def _format_sse(event: str, data_obj: dict) -> str:
    payload = json.dumps(data_obj, separators=(",", ":"))
    return f"event: {event}\ndata: {payload}\n\n"


app = create_app()
